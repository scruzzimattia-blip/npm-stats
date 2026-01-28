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

## Struktur

```
npm-monitor/
├── src/
│   ├── app.py          # Streamlit Dashboard
│   ├── config.py       # Konfiguration
│   ├── database.py     # DB-Operationen
│   ├── log_parser.py   # Log-Parsing
│   └── utils.py        # Hilfsfunktionen
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env                # Konfiguration (nicht committen!)
└── .env.example        # Beispiel-Konfiguration
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

## Gefilterte IPs

Automatisch gefiltert werden:
- Private Netzwerke (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Localhost (127.0.0.0/8)
- Cloudflare IPs (alle offiziellen Bereiche)
- Benutzerdefinierte IPs (via `IGNORED_IPS`)

## Lizenz

MIT
