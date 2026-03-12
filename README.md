# NPM Monitor 🌐

Ein leistungsstarkes, modernes Multi-Container Monitoring-Dashboard für den **Nginx Proxy Manager (NPM)** mit KI-Unterstützung, CrowdSec-Integration und geografischer Analyse.

![Version](https://img.shields.io/badge/version-1.0.0-green)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Architecture](https://img.shields.io/badge/architecture-Multi--Container-orange)
![AI](https://img.shields.io/badge/AI-OpenRouter-purple)

## 🚀 Kern-Features

- **🏗️ Multi-Container Architektur**: Getrennte Services für UI (`npm-ui`), Hintergrund-Verarbeitung (`npm-worker`) und KI-Analyse (`npm-ai`) für maximale Performance.
- **🤖 KI-Verhaltensanalyse**: Integrierte LLM-Analyse via **OpenRouter** (z.B. Gemini, DeepSeek). Erkennt automatisch böswillige Absichten hinter Log-Mustern.
- **🛡️ CrowdSec Integration**: Abgleich von IPs mit der globalen CrowdSec-Community-Datenbank für proaktiven Schutz.
- **🚫 Intelligentes Auto-Blocking**: Erkennt 404-Flooding, verdächtige Pfade und Anomalien. Sperrt IPs lokal (`iptables`) oder an der **Cloudflare Edge**.
- **📊 Echtzeit-Monitoring**: Live-Log-Viewer (5s Refresh), NPM-Health-Checks und Anomalie-Warnungen bei Traffic-Spikes.
- **🗺️ Geo-Visualisierung**: Interaktive Karten zur Identifizierung globaler Traffic-Quellen inkl. detaillierter Bot-Kategorisierung (Security Scanner, Suchmaschinen etc.).
- **🔔 Multi-Channel Alerting**: Benachrichtigungen via **Telegram**, **Discord** oder **Slack**.

## 🛠️ Installation & Setup

1. **Konfiguration vorbereiten**:
   ```bash
   cp .env.example .env
   # WICHTIG: Passwörter, API-Keys (OpenRouter, Cloudflare) und Telegram-Daten anpassen!
   nano .env
   ```

2. **Stack starten**:
   ```bash
   docker compose up -d --build
   ```

3. **Dashboard öffnen**: http://localhost:8501

## 📦 Service-Struktur

| Service | Aufgabe |
|---------|---------|
| `npm-ui` | Streamlit Dashboard & Benutzeroberfläche |
| `npm-worker` | Log-Parsing, DB-Synchronisation & Blocking-Logik |
| `npm-ai` | Hintergrund-KI-Analyse für blockierte IPs |
| `crowdsec` | Lokale CrowdSec API & Log-Security-Engine |
| `shared-postgres` | Zentrale Datenbank für alle Metriken & Berichte |
| `geoip-updater` | Automatischer Update der MaxMind Datenbank |

## ⚙️ Wichtige Konfigurationen (.env)

| Variable | Beschreibung |
|----------|--------------|
| `OPENROUTER_API_KEY` | Key für die KI-Verhaltensanalyse |
| `ENABLE_AI_AUTO_ANALYSIS` | Automatische KI-Prüfung bei jeder Sperre |
| `CLOUDFLARE_API_TOKEN` | Für Blocking auf Cloudflare Edge Ebene |
| `TELEGRAM_BOT_TOKEN` | Bot-Token für mobile Benachrichtigungen |
| `ENABLE_CROWDSEC` | Aktiviert die IP-Reputationsprüfung |

## 🛡️ Sicherheit & Analyse

NPM Monitor bietet nun eine vierstufige Verteidigung:
1. **Regelbasiert**: Schnelle Erkennung von Standardangriffen (Worker).
2. **Community**: Schutz durch globale Blocklisten (CrowdSec).
3. **KI-Unterstützt**: Tiefenanalyse von komplexen Verhaltensmustern (AI-Analyzer).
4. **Edge-Defense**: Blockiert Angriffe bevor sie den Server erreichen (Cloudflare).

## 📂 Projektstruktur

```
npm-monitor/
├── pages/              # Streamlit Multi-Page (Overview, IP-Analysis, etc.)
├── src/
│   ├── ai_analyzer.py  # KI-Logik & OpenRouter Integration
│   ├── crowdsec.py     # CrowdSec LAPI Schnittstelle
│   ├── cloudflare_waf.py # Cloudflare API Integration
│   ├── blocking.py     # Zentrale Blocking-Logik
│   └── database.py     # DB-Kern mit AI-Bericht-Speicherung
├── entrypoint-*.sh     # Spezialisierte Start-Skripte für Services
├── docker-compose.yml  # Multi-Container Definition
└── pyproject.toml      # Zentrale Abhängigkeiten (uv)
```

## ⚖️ Lizenz

MIT - Erstellt für maximale Sicherheit und Transparenz deines NPM-Traffics.
