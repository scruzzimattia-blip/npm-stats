import logging
import requests
from datetime import datetime, timedelta, timezone
from src.config import app_config
from src.database import get_connection, add_ai_report

logger = logging.getLogger(__name__)

class DailyBriefingGenerator:
    """Generate daily security briefings using AI."""

    def __init__(self):
        self.api_key = app_config.openrouter_api_key
        self.model = app_config.ai_model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate_briefing(self) -> str:
        """Analyze last 24h of traffic and generate a Markdown briefing."""
        if not self.api_key:
            return "Fehler: OpenRouter API Key fehlt."

        # 1. Gather 24h context
        context = self._get_24h_summary()
        
        # 2. Build Prompt
        prompt = f"""Analysiere den Traffic der letzten 24 Stunden meines Nginx Proxy Managers.
Identifiziere Trends, auffällige Anomalien und schlage proaktiv neue Sicherheitsregeln vor.

Zusammenfassung der Daten (letzte 24h):
{context}

Erstelle einen 'Daily Morning Briefing' Bericht im Markdown-Format für den Admin.
Gliedere ihn in:
- **Status-Übersicht**: (Wie war der Traffic im Vergleich zum Vortag?)
- **Top Bedrohungen**: (Welche IPs/ASNs waren besonders bösartig?)
- **Proaktive Empfehlungen**: (Welche Pfade sollten wir sperren? Welche ASN sollte blockiert werden?)
- **KI-Fazit**: (Ein kurzer Satz zur Gesamtsicherheitslage)
"""

        # 3. Request to OpenRouter
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mattia/npm-monitor",
                    "X-Title": "NPM Monitor Daily Briefing"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Du bist ein Senior Security Analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5
                },
                timeout=60
            )
            response.raise_for_status()
            briefing = response.json()["choices"][0]["message"]["content"]
            
            # Save as a special AI report for "SYSTEM"
            add_ai_report("SYSTEM_BRIEFING", briefing, "Information", self.model)
            return briefing
        except Exception as e:
            logger.error(f"Failed to generate daily briefing: {e}")
            return f"Fehler bei der Generierung: {str(e)}"

    def _get_24h_summary(self) -> str:
        """Collect aggregated stats for the last 24h."""
        summary = []
        try:
            import psycopg.rows as psycopg_rows
            query = """
                SELECT host, path, status, COUNT(*) as count
                FROM traffic
                WHERE time >= NOW() - INTERVAL '24 hours'
                GROUP BY host, path, status
                ORDER BY count DESC
                LIMIT 30;
            """
            with get_connection() as conn:
                with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
                    for r in rows:
                        summary.append(f"- {r['host']}{r['path']} (Status {r['status']}): {r['count']} mal")
        except Exception as e:
            summary.append(f"Fehler beim Laden der Daten: {e}")
            
        return "\n".join(summary)
