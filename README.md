# NPM Monitor 🌐

Ein leistungsstarkes, modernes Multi-Container Monitoring-Dashboard für den **Nginx Proxy Manager (NPM)** mit KI-Unterstützung, CrowdSec-Integration und geografischer 3D-Analyse.

![Version](https://img.shields.io/badge/version-1.6.1-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Architecture](https://img.shields.io/badge/architecture-Multi--Container-orange)
![AI](https://img.shields.io/badge/AI-OpenRouter-purple)

## 🚀 Kern-Features

- **🏗️ Multi-Container Architektur**: Getrennte spezialisierte Services für UI (`npm-ui`), Hintergrund-Worker (`npm-worker`) und KI-Analyse (`npm-ai`).
- **🤖 KI-Verhaltensanalyse & Assistent**: 
    - Automatische Verhaltensprüfung blockierter IPs via **OpenRouter** (Gemini, DeepSeek).
    - Interaktiver **KI-Chatbot** zur Abfrage von Log-Zusammenhängen und Sicherheits-Insights.
- **🛡️ Ganzheitliche Abwehr**: 
    - **CrowdSec Integration**: Echtzeit-Reputationsprüfung gegen globale Blocklisten.
    - **Cloudflare WAF**: Automatisches Blocking direkt an der Edge.
    - **Honey-Paths**: Sofortige permanente Sperre bei Zugriff auf sensible Pfade (z.B. `/.env`).
    - **ASN-Blocking**: Sperren ganzer Rechenzentren oder Provider-Netzwerke.
    - **Rate-Limiting**: Intelligenter Schutz vor Flooding und Brute-Force.
- **📊 Monitoring & Visualisierung**: 
    - **3D Live Threat Map**: Animierte Weltkarte mit Laser-Strahlen (Attack-Arcs).
    - **Uptime & SSL Monitor**: Überwachung deiner NPM-Hosts inkl. Zertifikats-Ablaufwarnung.
    - **NPM Host Discovery**: Automatische Erkennung deiner Proxy-Hosts aus der NPM-Datenbank.
- **👥 Multi-User Management**: Rollenbasierter Zugriff (Admin/Viewer) mit sicher gehashten Passwörtern.
- **🔔 Multi-Channel Alerting**: Sofortige Benachrichtigungen via **Telegram**, **Discord** oder **Slack**.

## 🛠️ Installation & Setup

1. **Konfiguration vorbereiten**:
   ```bash
   cp .env.example .env
   # WICHTIG: API-Keys (OpenRouter, Cloudflare), DB-Passwörter und Telegram-Daten anpassen!
   nano .env
   ```

2. **Stack starten**:
   ```bash
   docker compose up -d --build
   ```

3. **Dashboard öffnen**: http://localhost:8501

## 📦 Service-Struktur

| Service | Aufgabe | Port (intern) |
|---------|---------|---------------|
| `npm-ui` | Streamlit Dashboard & KI-Assistant | 8501 |
| `npm-worker` | Log-Parsing, Uptime-Check & Blocking | - |
| `npm-ai` | Hintergrund-KI-Analyse für blockierte IPs | - |
| `crowdsec` | Lokale CrowdSec LAPI Security-Engine | 8080 |
| `shared-postgres` | Zentrale Datenbank (Metriken, Berichte, User) | 5432 |

## ⚙️ Wichtige Konfigurationen (.env)

| Variable | Beschreibung | Standard |
|----------|--------------|----------|
| `OPENROUTER_API_KEY` | Key für die KI-Verhaltensanalyse | - |
| `ENABLE_AI_AUTO_ANALYSIS` | Automatische KI-Prüfung bei jeder Sperre | `false` |
| `HONEY_PATHS` | Pfade für Sofort-Sperre (kommagetrennt) | `/.env,/.git,...` |
| `MAX_REQUESTS_PER_MINUTE` | Globales Rate-Limit pro IP | `60` |
| `NPM_DB_TYPE` | NPM Datenbank-Typ (mysql/sqlite) | `mysql` |

## 🛡️ Die vier Verteidigungslinien

NPM Monitor schützt deinen Server proaktiv in vier Stufen:
1. **Lokal (Worker)**: Erkennt 404-Flooding, Brute-Force und Honey-Path Zugriffe.
2. **Community (CrowdSec)**: Nutzt kollektive Intelligenz zur Erkennung bekannter Angreifer.
3. **KI-Ebene (AI-Analyzer)**: Versteht komplexe Angriffsmuster und Absichten.
4. **Edge (Cloudflare)**: Stoppt Angriffe, bevor sie deine Leitung belasten.

## 📂 Projektstruktur

```
npm-monitor/
├── pages/              # UI-Seiten (Overview, Analysis, Blocking, AI-Assistant, Settings)
├── src/
│   ├── ai_analyzer.py  # Hintergrund-KI-Logik
│   ├── blocking.py     # Zentrale Abwehr-Logik (Honey-Paths, ASN, Rate-Limit)
│   ├── auth.py         # DB-gestützte Benutzerverwaltung
│   ├── database.py     # Datenbank-Kern (PostgreSQL)
│   └── utils/
│       ├── npm_sync.py # NPM-Datenbank Integration & Uptime-Check
│       └── ai_assistant.py # Chatbot-Backend
├── docker-compose.yml  # Multi-Container Stack
└── pyproject.toml      # Paket-Verwaltung (uv)
```

## ⚖️ Lizenz

MIT - Erstellt für maximale Sicherheit und Transparenz deines NPM-Traffics.
