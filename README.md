# NPM Monitor

Traffic-Monitoring-Dashboard für Nginx Proxy Manager (NPM).

## Features

- **Echtzeit-Monitoring**: Automatische Synchronisation von NPM Access Logs
- **Traffic-Analyse**: Requests pro Stunde, Statuscodes, Top-Domains und -Pfade
- **IP-Filterung**: Automatisches Filtern von privaten IPs, Cloudflare und benutzerdefinierten IPs
- **GeoIP** (optional): Länder- und Städte-Erkennung für Besucher
- **Browser-Analyse**: Erkennung von Browser, OS und Gerätetyp
- **Zeitraum-Filter**: Vordefinierte Zeiträume oder eigene Datumsauswahl
- **CSV-Export**: Exportiere gefilterte Daten
- **Daten-Retention**: Automatische Bereinigung alter Daten
- **Connection Pooling**: Effiziente Datenbankverbindungen
- **Health Checks**: Docker Health Checks für zuverlässigen Betrieb
- **Sicherheit**: Passwort-Authentifizierung und IP-basierte Zugriffskontrolle
- **🚫 Auto-Blocking**: Automatische IP-Sperrung bei Angriffsmustern (Fail2Ban-ähnlich)

## Installation

1. `.env`-Datei anpassen:

```bash
cp .env.example .env
# Passwort ändern!
nano .env
```

2. Container starten:

```bash
docker compose up -d --build
```

3. Dashboard öffnen: http://localhost:8501

## Konfiguration

### Umgebungsvariablen

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `DB_PASSWORD` | - | **Pflicht**: Datenbank-Passwort |
| `DB_HOST` | npm-monitor-db | PostgreSQL Host |
| `DB_PORT` | 5432 | PostgreSQL Port |
| `DB_NAME` | npm_monitor | Datenbankname |
| `DB_USER` | npm_user | Datenbankbenutzer |
| `LINES_PER_FILE` | 10000 | Max. Zeilen pro Log-Datei |
| `MAX_DISPLAY_ROWS` | 50000 | Max. angezeigte Zeilen |
| `RETENTION_DAYS` | 30 | Tage bis zur Datenbereinigung |
| `ENABLE_GEOIP` | false | GeoIP aktivieren |
| `IGNORED_IPS` | - | Komma-getrennte IPs zum Ignorieren |
| `ENABLE_AUTH` | true | Authentifizierung aktivieren |
| `AUTH_USERNAME` | admin | Dashboard-Benutzername |
| `AUTH_PASSWORD` | - | **Pflicht**: Dashboard-Passwort |
| `ALLOWED_NETWORKS` | 127.0.0.1/32 | Erlaubte IP-Netzwerke (comma-separiert) |

### GeoIP aktivieren

1. MaxMind GeoLite2 City Datenbank herunterladen (kostenlose Registrierung erforderlich):
   https://dev.maxmind.com/geoip/geolite2-free-geolocation-data

2. Datenbank in `./geoip/GeoLite2-City.mmdb` ablegen

3. In `docker-compose.yml` das GeoIP-Volume aktivieren:
```yaml
volumes:
  - ./geoip:/geoip:ro
```

4. In `.env` aktivieren:
```
ENABLE_GEOIP=true
```

5. Container neu starten:
```bash
docker compose up -d --build
```

## Sicherheit

### Authentifizierung

NPM Monitor bietet zwei Sicherheitsebenen:

1. **Passwort-Authentifizierung**: 
   - Setze `ENABLE_AUTH=true` (Standard)
   - Konfiguriere `AUTH_USERNAME` und `AUTH_PASSWORD`
   - Sessions werden automatisch verwaltet

2. **IP-basierte Zugriffskontrolle**:
   - Beschränke Zugriff auf bestimmte Netzwerke mit `ALLOWED_NETWORKS`
   - Beispiel: `ALLOWED_NETWORKS=192.168.1.0/24,10.0.0.0/8`
   - Standard: Nur Localhost (`127.0.0.1/32`)

### Best Practices

- Ändere das Standard-Passwort sofort
- Verwende starke Passwörter (min. 12 Zeichen)
- Beschränke `ALLOWED_NETWORKS` auf vertrauenswürdige Netze
- Verwende HTTPS über einen Reverse Proxy
- Halte MaxMind API-Keys geheim
- Commite niemals `.env` Dateien

### Sicherheitshärtung

Docker Container sind bereits gesichert:
- Non-root User (appuser)
- Read-only Dateisystem
- `no-new-privileges` Security Option
- Netzwerk-Isolation (internal network)
- Resource Limits (1GB RAM, 1 CPU)

## Struktur

```
npm-monitor/
├── src/
│   ├── app.py          # Streamlit Dashboard
│   ├── auth.py         # Authentifizierung
│   ├── config.py       # Konfiguration
│   ├── database.py     # DB-Operationen
│   ├── log_parser.py   # Log-Parsing
│   ├── sync.py         # Log-Synchronisation
│   ├── utils.py        # Hilfsfunktionen
│   └── components/    # UI-Komponenten
│       ├── charts.py
│       ├── tables.py
│       └── sidebar.py
├── tests/             # Test-Suite
├── docs/              # Dokumentation
│   ├── API.md
│   └── ARCHITECTURE.md
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml     # Python-Projektkonfiguration
├── .env               # Konfiguration (nicht committen!)
└── .env.example       # Beispiel-Konfiguration
```

## Wartung

### Logs prüfen

```bash
docker compose logs -f npm-monitor
```

### Datenbank zurücksetzen

```bash
docker compose down
rm -rf db-data
docker compose up -d
```

### Manueller Daten-Export

Im Dashboard den "CSV Export" Button verwenden.

## 🔥 Host-basiertes Firewall-Blocking

### Schnellstart (Ein-Klick-Installation)

```bash
# Auf dem HOST-System ausführen
cd ~/npm-stats
sudo ./scripts/install-iptables.sh

# Das war's! Das Script macht alles automatisch:
# ✅ Installiert Sync-Script
# ✅ Verbindet zur Datenbank
# ✅ Installiert Systemd Service
# ✅ Startet automatische Synchronisation (jede Minute)
```

### Dashboard-Integration

Das Blocking-Dashboard ist im Web-UI integriert:

1. **Dashboard öffnen**: http://localhost:8501
2. **Tab "🚫 Blocked IPs"** anklicken
3. **Geblockte IPs** werden mit Grund und Zeitstempel angezeigt
4. **Manuelles Entsperren**: IPs auswählen und "Unblock Selected IPs" klicken

### Automatische Prozesse

| Komponente | Intervall | Beschreibung |
|------------|-----------|--------------|
| **Log-Sync** | 60s | Neue Logs einlesen |
| **Angriffserkennung** | Echtzeit | Während Log-Sync |
| **iptables-Sync** | 60s | Host-Firewall aktualisieren |
| **Daten-Cleanup** | 86400s | Alte Blocks entfernen |

### Workflow

```
Angriff erkannt (NPM Container)
        ↓
Block in Datenbank speichern
        ↓
Host-Script liest DB (jede Minute)
        ↓
iptables DROP-Regel erstellen
        ↓
Traffic wird GEDROPPT (Host-Level)
        ↓
Dashboard zeigt Block an
```

### Status prüfen

```bash
# Service-Status
sudo systemctl status npm-monitor-iptables.timer

# Geblockte IPs in iptables
sudo iptables -L NPM_MONITOR -n -v

# In der Datenbank
docker compose exec npm-monitor python3 -c "
from src.database import get_blocked_ips
ips = get_blocked_ips(active_only=True)
print(f'{len(ips)} IPs currently blocked')
for ip, reason, blocked_at, block_until, is_manual in ips[:5]:
    print(f'  {ip}: {reason}')
"

# Logs
sudo journalctl -u npm-monitor-iptables -f
```

### Manuelle IP-Blockierung

```bash
# Über Dashboard
# 1. Tab "🚫 Blocked IPs"
# 2. IPs werden automatisch angezeigt
# 3. Zum Entsperren: Checkbox auswählen → "Unblock Selected IPs"

# Über Datenbank
docker compose exec npm-monitor python3 -c "
from src.database import add_blocked_ip
from datetime import datetime, timedelta

# IP für 1 Stunde blockieren
add_blocked_ip('192.168.1.100', 'Manual block', datetime.now() + timedelta(hours=1))
print('IP blocked')
"

# Über Host-iptables
sudo iptables -A NPM_MONITOR -s 192.168.1.100 -j DROP -m comment --comment "manual"
```

### Automatische Installation

Das Install-Script macht alles automatisch:
- ✅ Installiert iptables-Sync-Script
- ✅ Erstellt Konfiguration
- ✅ Installiert Systemd Timer
- ✅ Testet Datenbank-Verbindung
- ✅ Startet Service

### Manuelle Installation

Siehe [docs/HOST_IPTABLES.md](docs/HOST_IPTABLES.md) für detaillierte Anleitung.

### Status prüfen

```bash
# Service-Status
sudo systemctl status npm-monitor-iptables.timer

# Logs
sudo journalctl -u npm-monitor-iptables -f

# Geblockte IPs
sudo iptables -L NPM_MONITOR -n -v
```

## Gefilterte IPs

Automatisch gefiltert werden:
- Private Netzwerke (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Localhost (127.0.0.0/8)
- Cloudflare IPs (alle offiziellen Bereiche)
- Benutzerdefinierte IPs (via `IGNORED_IPS`)

## Entwicklung

### Tests ausführen

```bash
# Alle Tests
python3 -m pytest tests/ -v

# Mit Coverage
python3 -m pytest tests/ --cov=src --cov-report=html

# Spezifischer Test
python3 -m pytest tests/test_database.py -v
```

### Code-Qualität

```bash
# Linting
ruff check src/

# Formatierung
ruff format src/

# Pre-commit hooks
pre-commit run --all-files
```

### Beitragen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Richtlinien.

## 🚫 Auto-Blocking (Fail2Ban-ähnlich)

NPM Monitor kann IPs automatisch sperren, die verdächtige Aktivitäten zeigen.

### Wie es funktioniert

1. **Angriffserkennung**: Überwacht Traffic auf verdächtige Muster
2. **Schwellwerte**: Sperrt bei Überschreitung konfigurierter Limits
3. **Automatische Sperrung**: Blockiert IPs temporär
4. **Dashboard**: Verwaltung gesperrter IPs über UI

### Erkannte Angriffsmuster

- **404-Fehler**: Zu viele nicht existierende Seiten angefordert
- **403-Fehler**: Zu viele verbotene Zugriffe
- **5xx-Fehler**: Zu viele Server-Fehler verursacht
- **Verdächtige Pfade**: Zugriff auf `/wp-admin`, `/phpmyadmin`, `.env`, etc.
- **Gesamt-Fehler**: Zu viele fehlgeschlagene Requests

### Konfiguration

```bash
# Blocking aktivieren/deaktivieren
ENABLE_BLOCKING=true

# Sperrdauer (Sekunden)
BLOCK_DURATION=3600  # 1 Stunde

# Schwellwerte
MAX_404_ERRORS=20      # Max. 404-Fehler pro 5 Minuten
MAX_403_ERRORS=10      # Max. 403-Fehler pro 5 Minuten
MAX_5XX_ERRORS=50      # Max. 5xx-Fehler pro 5 Minuten
MAX_FAILED_REQUESTS=100  # Max. fehlgeschlagene Requests pro 5 Minuten

# Verdächtige Pfade (comma-separiert)
SUSPICIOUS_PATHS=/wp-admin,/wp-login.php,/phpmyadmin,.env,.git
```

### IP-Whitelist

IPs können von der Sperrung ausgenommen werden:

```python
from src.blocking import get_blocker

blocker = get_blocker()
blocker.whitelist_ip("192.168.1.100")
```

### Manuelle Verwaltung

Über das Dashboard können gesperrte IPs:
- Angesehen werden (mit Grund und Dauer)
- Manuell entsperrt werden
- Zur Whitelist hinzugefügt werden

## Lizenz

MIT
