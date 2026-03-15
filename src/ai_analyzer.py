"""AI-powered log analyzer using OpenRouter."""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

import requests

# Add parent directory to path
sys.path.insert(0, str(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))))

from src.config import app_config
from src.database import get_connection, add_ai_report, get_ai_reports
from src.utils import setup_logging

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True

class AIAnalyzer:
    """Analyze suspicious IP behavior using LLMs via OpenRouter."""

    def __init__(self):
        self.api_key = app_config.openrouter_api_key
        self.model = app_config.ai_model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def analyze_ip(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Perform AI analysis for a specific IP based on its recent traffic."""
        if not self.api_key:
            logger.warning("OpenRouter API key not configured. Skipping AI analysis.")
            return None

        # 1. Collect context from DB
        context = self._get_ip_context(ip_address)
        if not context or not context.get("logs"):
            logger.info(f"No sufficient logs for AI analysis of {ip_address}")
            return None

        # 2. Build Prompt
        prompt = self._build_prompt(ip_address, context)

        # 3. Call OpenRouter
        try:
            logger.info(f"Sending AI analysis request for {ip_address} to {self.model}...")
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mattia/npm-monitor",
                    "X-Title": "NPM Monitor"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Du bist ein Senior SOC Analyst. Antworte ausschließlich in validem JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": { "type": "json_object" }
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
            
            # Parse JSON response
            try:
                # Remove possible markdown code blocks if the LLM adds them despite the system prompt
                clean_json = raw_content.replace("```json", "").replace("```", "").strip()
                res = json.loads(clean_json)
                
                content = res.get("markdown_report", raw_content)
                threat_level = res.get("bedrohungslevel", "Unknown")
                category = res.get("kategorie", "Unknown")
                
                full_report = f"### KI Analyse: {category}\n\n**Beurteilung:** {res.get('beurteilung')}\n**Begründung:** {res.get('begruendung')}\n\n{content}"
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI JSON response for {ip_address}. Falling back to raw text.")
                full_report = raw_content
                threat_level = "Unknown"

            # 4. Save to DB
            add_ai_report(ip_address, full_report, threat_level, self.model)
            logger.info(f"AI analysis completed for {ip_address}. Threat Level: {threat_level}")
            return {"report": full_report, "threat_level": threat_level}

        except Exception as e:
            logger.error(f"AI analysis failed for {ip_address}: {e}")
            return None

    def _get_ip_context(self, ip_address: str) -> Dict[str, Any]:
        """Fetch recent log history for the IP as context with GeoIP info."""
        query = """
            SELECT time, host, method, path, status, user_agent, response_length, country_code, city
            FROM traffic
            WHERE remote_addr = %s
            ORDER BY time DESC
            LIMIT 100;
        """
        import psycopg.rows as psycopg_rows
        with get_connection() as conn:
            with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                cur.execute(query, (ip_address,))
                logs = cur.fetchall()
                
        # Get blocking reason if available
        reason = "Unbekannt"
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT reason FROM blocklist WHERE ip_address = %s LIMIT 1", (ip_address,))
                    row = cur.fetchone()
                    if row: reason = row[0]
        except Exception:
            pass

        return {"logs": logs, "block_reason": reason}

    def _build_prompt(self, ip_address: str, context: Dict[str, Any]) -> str:
        """Create a highly detailed security analysis prompt."""
        log_lines = []
        country = "Unbekannt"
        for log in context["logs"]:
            if log.get("country_code"): country = f"{log['country_code']} ({log.get('city', 'Unbekannt')})"
            line = f"[{log['time']}] {log['method']} {log['host']}{log['path']} -> {log['status']} (UA: {log['user_agent']})"
            log_lines.append(line)
            
        logs_str = "\n".join(log_lines)
        
        return f"""Du bist ein Senior SOC Analyst. Analysiere das Verhalten der IP {ip_address} aus {country}.
Die IP wurde gesperrt mit dem Grund: "{context.get('block_reason', 'Unbekannt')}".

Deine Aufgabe ist es, die Absicht des Akteurs zu bestimmen. Suche nach:
1. Directory/File Bruteforce (viele 404s auf sensitive Pfade)
2. Vulnerability Scanning (Suche nach .env, .git, /wp-admin, phpmyadmin)
3. Exploitation Versuche (SQL-Injection, LFI/RFI Muster, Command Injection)
4. Botnet-Verhalten (Automatisierte, repetitive Anfragen mit untypischen User-Agents)
5. Harmloses Verhalten (Suchmaschinen-Crawler, Fehlkonfiguration des Nutzers)

Letzte Logs:
{logs_str}

ANTWORTE STRENG IM FOLGENDEN JSON-FORMAT (NUR DAS JSON!):
{{
  "beurteilung": "Mensch/Harmloser Bot/Bösartiger Akteur",
  "bedrohungslevel": "Low/Medium/High/Critical",
  "kategorie": "Bruteforce/SQLi/Scanner/Crawler/etc",
  "begruendung": "Kurze technische Analyse der Muster",
  "empfehlung": "Permanent blocken / Beobachten / Whitelisten",
  "markdown_report": "Ein ausführlicher Bericht im Markdown-Format für das Dashboard"
}}
"""

def run_ai_loop() -> None:
    """Periodically check for newly blocked IPs that haven't been analyzed yet."""
    setup_logging()
    logger.info("Starting AI-Analyzer background loop...")
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    while not shutdown_requested:
        # Load latest settings from DB (including API keys)
        app_config.load_dynamic_settings()
        
        if app_config.enable_ai_auto_analysis and app_config.openrouter_api_key:
            analyzer = AIAnalyzer()
            try:
                # Find IPs that are blocked but have no AI report yet
                query = """
                    SELECT DISTINCT b.ip_address
                    FROM blocklist b
                    LEFT JOIN ai_analysis a ON b.ip_address = a.ip_address
                    WHERE a.id IS NULL
                    LIMIT 5;
                """
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query)
                        ips_to_analyze = [row[0] for row in cur.fetchall()]
                
                for ip in ips_to_analyze:
                    if shutdown_requested: break
                    analyzer.analyze_ip(ip)
                    time.sleep(2) # rate limiting
                    
            except Exception as e:
                logger.error(f"Error in AI loop: {e}")
        elif not app_config.openrouter_api_key:
            logger.debug("AI analysis active but OPENROUTER_API_KEY is missing. Waiting...")
        
        # Wait for next check
        time.sleep(30)

if __name__ == "__main__":
    run_ai_loop()
