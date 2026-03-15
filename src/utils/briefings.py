"""AI-powered security briefings and reports."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..config import app_config
from ..database import get_connection

logger = logging.getLogger(__name__)

class SecurityBriefing:
    """Generate security summaries using AI."""

    def __init__(self):
        from ..ai_analyzer import AIAnalyzer
        self.analyzer = AIAnalyzer()

    def generate_daily_summary(self) -> Optional[str]:
        """Generate a summary of the last 24 hours of security activity."""
        if not app_config.openrouter_api_key:
            return "KI-Zusammenfassung nicht verfügbar (API-Key fehlt)."

        # 1. Gather stats for the last 24h
        stats = self._get_last_24h_stats()
        if stats["total_requests"] == 0:
            return "Keine Traffic-Daten für die letzten 24 Stunden vorhanden."

        # 2. Build prompt
        prompt = f"""Du bist ein Senior Security Analyst. Erstelle eine prägnante Zusammenfassung der Sicherheitslage der letzten 24 Stunden.

Statistiken:
- Gesamt-Requests: {stats['total_requests']}
- Einzigartige IPs: {stats['unique_ips']}
- Blockierte IPs (neu): {stats['new_blocks']}
- Top blockierte Länder: {', '.join(stats['top_countries'])}
- Häufigste Angriffsvektoren: {', '.join(stats['top_reasons'])}

Wichtige Ereignisse:
{stats['events_summary']}

Erstelle einen kurzen, professionellen Bericht im Markdown-Format. Gehe auf Trends ein und gib eine kurze Empfehlung ab.
Antworte direkt mit dem Markdown-Bericht.
"""

        # 3. Call AI
        try:
            # We bypass the JSON requirement for the briefing report to get a nice markdown response
            # by calling requests directly or modifying the analyzer slightly
            # For simplicity, we'll use a direct call here or a special method
            response = self._call_ai_raw(prompt)
            return response
        except Exception as e:
            logger.error(f"Failed to generate daily summary: {e}")
            return None

    def _get_last_24h_stats(self) -> Dict[str, Any]:
        """Collect aggregated data for the briefing."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        stats = {
            "total_requests": 0,
            "unique_ips": 0,
            "new_blocks": 0,
            "top_countries": [],
            "top_reasons": [],
            "events_summary": "Keine kritischen Vorfälle."
        }

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Basic stats
                cur.execute("SELECT COUNT(*), COUNT(DISTINCT remote_addr) FROM traffic WHERE time >= %s", (yesterday,))
                row = cur.fetchone()
                stats["total_requests"] = row[0]
                stats["unique_ips"] = row[1]

                # Blocks
                cur.execute("SELECT COUNT(*) FROM blocklist WHERE blocked_at >= %s", (yesterday,))
                stats["new_blocks"] = cur.fetchone()[0]

                # Top countries
                cur.execute("""
                    SELECT country_code, COUNT(*) as c 
                    FROM traffic 
                    WHERE time >= %s AND country_code IS NOT NULL 
                    GROUP BY country_code ORDER BY c DESC LIMIT 3
                """, (yesterday,))
                stats["top_countries"] = [f"{r[0]} ({r[1]})" for r in cur.fetchall()]

                # Top reasons
                cur.execute("""
                    SELECT reason, COUNT(*) as c 
                    FROM blocklist 
                    WHERE blocked_at >= %s 
                    GROUP BY reason ORDER BY c DESC LIMIT 3
                """, (yesterday,))
                stats["top_reasons"] = [f"{r[0]} ({r[1]})" for r in cur.fetchall()]

        return stats

    def _call_ai_raw(self, prompt: str) -> str:
        """Direct call to OpenRouter without JSON enforcement."""
        import requests
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {app_config.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": app_config.ai_model,
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
