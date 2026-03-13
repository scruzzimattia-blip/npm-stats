"""AI Assistant for log analysis and security insights."""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from src.config import app_config
from src.database import get_connection

logger = logging.getLogger(__name__)

class AIAssistant:
    """Chat-based assistant for interacting with NPM Monitor data."""

    def __init__(self):
        self.api_key = app_config.openrouter_api_key
        self.model = app_config.ai_model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def ask(self, question: str, chat_history: List[Dict[str, str]] = None) -> Optional[str]:
        """Ask the AI a question about the logs or security status."""
        if not self.api_key:
            return "Fehler: OpenRouter API Key ist nicht konfiguriert."

        # 1. Gather general context (last 100 logs, blocklist summary)
        context = self._get_system_context()
        
        # 2. Build Messages
        messages = [
            {
                "role": "system", 
                "content": (
                    "Du bist der NPM Monitor KI-Assistent. Du hilfst dem Administrator, seinen Traffic zu verstehen. "
                    "Dir stehen die neuesten Logs und Sperrlisten-Daten zur Verfügung. Antworte präzise und technisch fundiert. "
                    "Verwende Markdown für die Formatierung."
                )
            },
            {
                "role": "user", 
                "content": f"Hier ist der aktuelle System-Kontext:\n{context}\n\nBenutzerfrage: {question}"
            }
        ]
        
        if chat_history:
            # Insert history between system and current user message
            for msg in chat_history[-5:]: # Keep last 5 for context
                messages.insert(1, msg)

        # 3. Request to OpenRouter
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mattia/npm-monitor",
                    "X-Title": "NPM Monitor Assistant"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=45
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"AI Assistant request failed: {e}")
            return f"Fehler bei der KI-Anfrage: {str(e)}"

    def _get_system_context(self) -> str:
        """Gather recent logs and blocking stats as context for the chat."""
        context_parts = []
        
        # Latest Blocks
        try:
            from src.database import get_blocklist_with_ai_status
            blocks = get_blocklist_with_ai_status()[:10]
            if blocks:
                context_parts.append("Aktuelle Sperren:")
                for b in blocks:
                    context_parts.append(f"- IP: {b['ip_address']}, Grund: {b['reason']}, Bis: {b['block_until']}")
        except Exception:
            pass

        # Recent Log Summary
        try:
            import psycopg.rows as psycopg_rows
            query = """
                SELECT host, method, path, status, COUNT(*) as count
                FROM traffic
                WHERE time >= NOW() - INTERVAL '1 hour'
                GROUP BY host, method, path, status
                ORDER BY count DESC
                LIMIT 20;
            """
            with get_connection() as conn:
                with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
                    if rows:
                        context_parts.append("\nTop Traffic (letzte Stunde):")
                        for r in rows:
                            context_parts.append(f"- {r['method']} {r['host']}{r['path']} (Status {r['status']}): {r['count']} mal")
        except Exception:
            pass

        return "\n".join(context_parts)
