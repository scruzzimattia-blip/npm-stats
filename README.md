# NPM Monitor 🌐

Ein leistungsstarkes, modernes Traffic-Monitoring-Dashboard für den **Nginx Proxy Manager (NPM)** mit Fokus auf Performance, Sicherheit und geografische Analyse.

![Version](https://img.shields.io/badge/version-0.2.0-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Streamlit](https://img.shields.io/badge/frontend-Streamlit-red)
![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-blue)

## 🚀 Kern-Features

- **📊 Multi-Page Dashboard**: Klare Trennung zwischen Übersicht, detaillierter IP-Analyse, Sicherheitsverwaltung und Systemeinstellungen.
- **🚫 Intelligentes Auto-Blocking**: Erkennt Angriffsmuster (404-Flooding, verdächtige Pfade) und sperrt IPs automatisch.
  - **Shared State**: Nutzt die Datenbank zur Synchronisation der Zähler zwischen Hintergrund-Worker und Dashboard.
  - **Host-Integration**: Synchronisiert DB-Sperren direkt mit der Host-Firewall (`iptables`) für maximale Effizienz.
- **🗺️ Geo-Visualisierung**: Interaktive 3D-Heatmap und Cluster-Karte zur Identifizierung globaler Traffic-Quellen.
- **🔔 Echtzeit-Alerting**: Sofortige Benachrichtigungen via **Discord**, **Slack** oder **Telegram** Webhooks bei IP-Sperrungen.
- **📄 PDF-Reporting**: Generiere professionelle Traffic-Berichte mit einem Klick.
- **⚡ High Performance**: Optimiert für große Datenmengen durch PostgreSQL-Indizes, serverseitige Aggregation und intelligentes Caching.

## 🛠️ Installation & Setup

1. **Konfiguration vorbereiten**:
   ```bash
   cp .env.example .env
   # WICHTIG: Passwörter und WEBHOOK_URL anpassen!
   nano .env
   ```

2. **Container starten**:
   ```bash
   docker compose up -d --build
   ```

3. **Host-Firewall Blocking (Optional, empfohlen)**:
   ```bash
   # Auf dem HOST-System ausführen, um DB-Sperren mit iptables zu verbinden
   cd ~/npm-stats
   sudo ./scripts/install-iptables.sh
   ```

4. **Dashboard öffnen**: http://localhost:8501

## ⚙️ Konfiguration (.env)

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `WEBHOOK_URL` | - | Webhook-URL für Discord/Slack Benachrichtigungen |
| `NOTIFY_ON_BLOCK` | `true` | Benachrichtigung bei automatischer Sperre senden |
| `ENABLE_GEOIP` | `true` | Geografische Erkennung aktivieren |
| `RETENTION_DAYS` | `30` | Aufbewahrungsdauer der Logs in Tagen |
| `SYNC_INTERVAL` | `60` | Log-Synchronisation alle X Sekunden |
| `BLOCK_DURATION` | `3600` | Standard-Sperrdauer in Sekunden (1 Std) |

## 🛡️ Sicherheit & Blocking

NPM Monitor bietet ein mehrstufiges Sicherheitskonzept:

1. **Analyse**: Der Hintergrund-Worker scannt kontinuierlich NPM-Logs auf Anomalien.
2. **Detection**: Überschreitet eine IP Schwellwerte (z.B. zu viele 404s oder Zugriff auf `/wp-admin`), wird sie in der Datenbank markiert.
3. **Action**: 
   - Die IP wird sofort in der App gesperrt.
   - Eine Benachrichtigung wird an den konfigurierten Webhook gesendet.
   - Das Host-Script wendet die Sperre auf Systemebene (`iptables DROP`) an.

## 📊 Dashboard-Struktur

- **Übersicht**: Echtzeit-Metriken, Traffic-Verlauf und Status-Verteilung.
- **IP-Analyse**: Wer besucht deine Seiten? Inklusive Weltkarte und Browser-Statistiken.
- **Blocking**: Liste aller aktiven Sperren, Gründe und manuelle Verwaltung (Entsperren/Whitelisting).
- **Einstellungen**: System-Status, Datenbank-Größe und Konfigurationsübersicht.

## 📈 Performance-Features

- **SQL-Aggregation**: Metriken werden direkt in der DB berechnet (schnell auch bei Millionen Einträgen).
- **Verbund-Indizes**: Optimierte Datenbank-Indizes für blitzschnelles Filtern nach Domain und Zeit.
- **Lazy Loading**: Logs werden paginiert geladen, um das UI flüssig zu halten.
- **Parallel Parsing**: Log-Dateien werden CPU-optimiert parallel eingelesen.

## 📂 Projektstruktur

```
npm-monitor/
├── pages/              # Streamlit Multi-Page Dateien
├── src/
│   ├── components/     # UI-Komponenten (Maps, Charts, Tables)
│   ├── utils/          # PDF-Export und Hilfsfunktionen
│   ├── blocking.py     # Angriffserkennung (Shared State)
│   ├── database.py     # Datenbank-Kern & Optimierungen
│   ├── notifications.py # Webhook-Integration
│   └── sync.py         # Log-Parser Integration
├── scripts/            # Host-Level Firewall Scripts
├── docker-compose.yml
└── pyproject.toml
```

## ⚖️ Lizenz

MIT - Erstellt für maximale Sicherheit und Transparenz deines NPM-Traffics.
