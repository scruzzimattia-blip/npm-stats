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
                        {"role": "system", "content": "You are a senior security analyst. Analyze the provided Nginx logs for malicious behavior. Be concise and technical. Format your response in Markdown."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": { "type": "json_object" } if "gemini" not in self.model.lower() else None
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Simple heuristic for threat level (usually LLMs include this in text)
            threat_level = "Unknown"
            if "HIGH" in content.upper() or "GEFÄHRLICH" in content.upper() or "CRITICAL" in content.upper():
                threat_level = "High"
            elif "MEDIUM" in content.upper() or "WARNUNG" in content.upper():
                threat_level = "Medium"
            else:
                threat_level = "Low"

            # 4. Save to DB
            add_ai_report(ip_address, content, threat_level, self.model)
            logger.info(f"AI analysis completed for {ip_address}. Threat Level: {threat_level}")
            return {"report": content, "threat_level": threat_level}

        except Exception as e:
            logger.error(f"AI analysis failed for {ip_address}: {e}")
            return None

    def _get_ip_context(self, ip_address: str) -> Dict[str, Any]:
        """Fetch recent log history for the IP as context."""
        query = """
            SELECT time, host, method, path, status, user_agent, response_length
            FROM traffic
            WHERE remote_addr = %s
            ORDER BY time DESC
            LIMIT 50;
        """
        import psycopg.rows as psycopg_rows
        with get_connection() as conn:
            with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                cur.execute(query, (ip_address,))
                logs = cur.fetchall()
                
        return {"logs": logs}

    def _build_prompt(self, ip_address: str, context: Dict[str, Any]) -> str:
        """Create a detailed prompt with log data."""
        log_lines = []
        for log in context["logs"]:
            line = f"{log['time']} | {log['host']} | {log['method']} {log['path']} | {log['status']} | {log['user_agent']}"
            log_lines.append(line)
            
        logs_str = "\n".join(log_lines)
        
        return f"""Analyze the following traffic from IP address {ip_address}.
Determine if this is a human, a harmless bot, or a malicious actor (scanners, exploit attempts, etc.).

Recent Logs:
{logs_str}

Please provide your analysis in Markdown format with the following sections:
- **Beurteilung**: (Human/Harmless Bot/Malicious)
- **Bedrohungslevel**: (Low/Medium/High/Critical)
- **Details**: (Why did you reach this conclusion? What patterns did you see?)
- **Empfehlung**: (What should I do? Permanent block, watch, etc.)
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
