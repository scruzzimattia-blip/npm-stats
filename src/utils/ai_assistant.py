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
        """Ask the AI a question about the logs or security status with rich context."""
        if not self.api_key:
            return "Fehler: OpenRouter API Key ist nicht konfiguriert."

        # 1. Gather rich context
        context = self._get_system_context()
        
        # 2. Add dynamic specific context based on question keywords
        specific_context = self._get_specific_context(question)
        if specific_context:
            context += f"\n\nZusätzliche Details für deine Analyse:\n{specific_context}"
        
        # 3. Build detailed System Prompt
        system_prompt = (
            "Du bist der NPM Monitor KI-Assistent, ein hochspezialisierter Senior Security Expert für Nginx Webserver-Sicherheit. "
            "Deine Aufgabe ist es, dem Administrator zu helfen, Bedrohungen zu identifizieren, Traffic-Muster zu verstehen und Sicherheitslücken zu schließen. "
            "\n\nRichtlinien für deine Antworten:"
            "\n- Sei präzise, technisch versiert und proaktiv."
            "\n- Wenn du nach Angriffen gefragt wirst, analysiere die Daten auf Muster wie SQLi, Path Traversal oder Botnet-Scanning."
            "\n- Gib konkrete Handlungsempfehlungen (z.B. 'IP permanent blocken', 'Pfade in Honey-Paths aufnehmen')."
            "\n- Nutze Markdown für eine übersichtliche Struktur (Listen, Fettdruck, Tabellen)."
            "\n- Beziehe dich direkt auf die unten stehenden System-Daten."
            "\n- Falls du einen Abuse-Report Entwurf erstellst, nutze ein professionelles englisches Format für den Provider."
            "\n- Antworte immer auf Deutsch (außer bei technischen Reports für Dritte)."
        )

        # 4. Build Messages
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": f"Aktueller Sicherheits-Status und Kontext:\n{context}\n\nBenutzer-Anfrage: {question}"
            }
        ]
        
        if chat_history:
            # Insert limited history
            for msg in chat_history[-10:]:
                messages.insert(1, msg)

        # 5. Request to OpenRouter
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mattia/npm-monitor",
                    "X-Title": "NPM Monitor Security Expert"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3, # Lower for better consistency
                    "max_tokens": 2000
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"AI Assistant request failed: {e}")
            return f"🚨 Fehler bei der KI-Anfrage: {str(e)}"

    def _get_specific_context(self, question: str) -> str:
        """Fetch additional data based on keywords in the question."""
        q_lower = question.lower()
        parts = []
        
        # 1. Abuse Report / Aggressive IP context
        if "abuse" in q_lower or "aggressiv" in q_lower or "report" in q_lower:
            try:
                # Find most aggressive IP in last hour
                query = """
                    SELECT remote_addr, COUNT(*) as count, 
                           COUNT(CASE WHEN status >= 400 THEN 1 END) as errors,
                           ARRAY_AGG(DISTINCT path) as targets
                    FROM traffic
                    WHERE time >= NOW() - INTERVAL '1 hour'
                    GROUP BY remote_addr
                    ORDER BY errors DESC, count DESC
                    LIMIT 3;
                """
                with get_connection() as conn:
                    import psycopg.rows as psycopg_rows
                    with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                        cur.execute(query)
                        rows = cur.fetchall()
                        if rows:
                            parts.append("Details zu den aktivsten IPs der letzten Stunde:")
                            for r in rows:
                                targets = ", ".join(r['targets'][:5])
                                parts.append(f"- IP {r['remote_addr']}: {r['count']} Anfragen, {r['errors']} Fehler. Ziele: {targets}")
            except Exception: pass

        # 2. 24h Analysis context
        if "24" in q_lower or "tag" in q_lower or "analyse" in q_lower:
            try:
                # Hourly distribution of errors
                query = """
                    SELECT DATE_TRUNC('hour', time) as hour, COUNT(*) as count
                    FROM traffic
                    WHERE time >= NOW() - INTERVAL '24 hours' AND status >= 400
                    GROUP BY hour
                    ORDER BY hour ASC;
                """
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query)
                        rows = cur.fetchall()
                        if rows:
                            dist = ", ".join([f"{r[0].strftime('%H')}h: {r[1]}" for r in rows])
                            parts.append(f"Fehler-Verteilung letzte 24h (Stunde: Anzahl): {dist}")
            except Exception: pass

        return "\n".join(parts)

    def _get_system_context(self) -> str:
        """Gather detailed recent logs, blocking stats, and top threats as context."""
        context_parts = []
        
        # 1. Global Metrics
        try:
            from src.database import get_database_info
            db_info = get_database_info()
            context_parts.append(f"System-Status: Gesamt-Requests: {db_info['total_rows']}, Aktive Sperren: {db_info['blocked_count']}")
        except Exception: pass

        # 2. Latest Blocks with AI Analysis
        try:
            from src.database import get_blocklist_with_ai_status
            blocks = get_blocklist_with_ai_status()[:15]
            if blocks:
                context_parts.append("\nKürzlich blockierte IPs:")
                for b in blocks:
                    threat = f" (KI Bedrohung: {b.get('threat_level')})" if b.get('threat_level') else ""
                    context_parts.append(f"- IP: {b['ip_address']}, Grund: {b['reason']}, Bis: {b['block_until']}{threat}")
        except Exception: pass

        # 3. Top Targets (Last 24h)
        try:
            import psycopg.rows as psycopg_rows
            query = """
                SELECT host, path, status, COUNT(*) as count
                FROM traffic
                WHERE time >= NOW() - INTERVAL '24 hours' AND status >= 400
                GROUP BY host, path, status
                ORDER BY count DESC
                LIMIT 15;
            """
            with get_connection() as conn:
                with conn.cursor(row_factory=psycopg_rows.dict_row) as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
                    if rows:
                        context_parts.append("\nTop Angriffsziele/Fehler (letzte 24h):")
                        for r in rows:
                            context_parts.append(f"- {r['host']}{r['path']} (Status {r['status']}): {r['count']} mal")
        except Exception: pass

        # 4. ASN Blocks
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT asn, description FROM asn_blocklist LIMIT 5")
                    asns = cur.fetchall()
                    if asns:
                        context_parts.append("\nBlockierte ASNs (Netzwerk-Sperren):")
                        for a in asns:
                            context_parts.append(f"- ASN {a[0]} ({a[1]})")
        except Exception: pass

        return "\n".join(context_parts)
