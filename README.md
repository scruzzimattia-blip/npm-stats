# NPM Monitor Enterprise 🌐 🛡️

Ein hochperformantes, KI-gestütztes Security-Ökosystem für den **Nginx Proxy Manager (NPM)**. NPM Monitor schützt deine Infrastruktur durch Echtzeit-Analyse, Täuschungsmanöver (Honeypots) und automatisierte Abwehr auf mehreren Ebenen.

![Version](https://img.shields.io/badge/version-2.0.0-gold)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Architecture](https://img.shields.io/badge/architecture-Microservice--API-orange)
![AI](https://img.shields.io/badge/AI-Autonomous-purple)

## 🚀 Enterprise-Highlights (V2 & V3)

- **🛡️ Auto-Healing Firewall**: Erkennt Manipulationen an der Firewall und stellt die `NPM_MONITOR` Sperrkette automatisch wieder her (alle 10 Min).
- **🏥 System Health Dashboard**: Zentrale Überwachung aller Komponenten (DB, Redis, Log-Worker, Firewall) auf einer neuen Status-Seite.
- **📜 Audit Logging**: Lückenlose Historie aller administrativen Aktionen wie Unblocks und Whitelisting für volle Revisionssicherheit.
- **🧪 Test Alert Function**: Teste deine Benachrichtigungskanäle (Webhook, Telegram, Email) direkt aus den Einstellungen.
- **⚡ High-Performance Caching**: Integration von **Redis** für ultraschnelles IP-Tracking und Rate-Limiting. Entlastet die Hauptdatenbank massiv.
- **📡 FastAPI Backend**: Ein neues, entkoppeltes REST-API-Backend auf Port **8001** für schnellen Datenzugriff und externe Integrationen.
- **📺 Live Monitor**: Echtzeit-Log-Streaming via Websockets und visuelle Darstellung von Angriffs-Strukturen als **Network Graph**.
- **🤖 KI-Autonomie & Briefings**: 
    - **Daily Security Briefing**: Die KI erstellt täglich eine Zusammenfassung der Sicherheitslage.
    - **JSON-Analysis**: Strukturierte Bedrohungserkennung mit hoher Präzision.
- **🍯 Deceptive Defense (Honeypots)**: Angreifer, die kritische Pfade wie `/.env` oder `/phpmyadmin` scannen, werden sofort für **1 Jahr** auf allen Ebenen (App, Firewall, Cloudflare) gesperrt.
- **📈 Skalierbare Daten**: Zeitbasierte **PostgreSQL-Partitionierung** und automatisierte **CSV-Archivierung** für Millionen von Log-Einträgen.
- **🔐 Hardened Auth**: Unterstützung für **Zwei-Faktor-Authentifizierung (MFA/TOTP)** über das Dashboard.
- **🔔 Multi-Channel Alerting**: Jetzt inklusive **E-Mail (SMTP)** Unterstützung zusätzlich zu Telegram und Discord.


## 🛠️ Installation & Enterprise Update

1. **Konfiguration**:
   ```bash
   cp .env.example .env
   # Neu: REDIS_URL und SMTP-Daten für Enterprise Features ergänzen!
   nano .env
   ```

2. **Stack bauen & starten**:
   ```bash
   # Da neue Services hinzugefügt wurden, ist ein Build erforderlich:
   docker compose up -d --build
   ```

3. **Dashboard & API**:
    - **UI**: http://localhost:8501
    - **API (Swagger)**: http://localhost:8001/docs

## 📦 Erweiterte Service-Struktur

| Service | Aufgabe | Port |
|---------|---------|------|
| `npm-ui` | Streamlit Dashboard & Live-Graph | 8501 |
| `npm-api` | FastAPI REST-Backend (Zentrale Datenquelle) | 8001 |
| `npm-worker` | Echtzeit-Log-Streaming & Blocking | 8000 (Metrics) |
| `npm-ai` | Hintergrund-KI-Analyse & Daily Briefings | - |
| `redis` | In-Memory Cache für IP-Tracking & Rate-Limits | 6379 |
| `shared-postgres` | Partitionierte Hauptdatenbank | 5432 |

## 🛡️ Die Enterprise-Verteidigungslinien

1. **Deceptive Defense**: Honeypots fangen Scanner sofort ab (1-Jahr-Sperre).
2. **Local WAF**: Erkennt SQLi, XSS und bösartige User-Agents in Millisekunden.
3. **Behavioral AI**: LLMs verstehen die Absicht hinter komplexen Angriffsmustern.
4. **Edge Defense**: Cloudflare blockt Angriffe, bevor sie deine Bandbreite nutzen.

## 📂 Projektstruktur

```
npm-monitor/
├── src/
│   ├── api/            # FastAPI Backend
│   ├── ai_analyzer.py  # KI-Logik (JSON-Mode)
│   ├── blocking.py     # WAF & Honeypot Kern
│   ├── database.py     # Partitionierung & Archivierung
│   └── utils/
│       ├── briefings.py # KI-Zusammenfassungen
│       └── reports.py   # PDF-Export
├── alembic/            # DB-Migrations-Versionen
└── docker-compose.yml  # Microservice Stack
```

## ⚖️ Lizenz

MIT - Entwickelt für höchste Sicherheitsansprüche im Nginx Proxy Manager Umfeld.
