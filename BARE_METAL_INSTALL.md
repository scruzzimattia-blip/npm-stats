# NPM Monitor: Bare-Metal Installation & Migration

Diese Anleitung beschreibt die Schritte, um den NPM Traffic Monitor direkt auf einem Linux-Server (ohne Docker) zu installieren und die Daten zu migrieren.

## 1. System-Abhängigkeiten installieren

Installiere PostgreSQL, Redis und die notwendigen Build-Tools:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib redis-server python3-pip
```

Stelle sicher, dass die Dienste laufen:

```bash
sudo systemctl enable --now postgresql
sudo systemctl enable --now redis-server
```

## 2. Lokale Datenbank vorbereiten

Erstelle den Datenbank-Benutzer und die Datenbank (ersetze `DEIN_PASSWORT` durch ein sicheres Passwort):

```bash
sudo -u postgres psql -c "CREATE USER npm_user WITH PASSWORD 'DEIN_PASSWORT';"
sudo -u postgres psql -c "CREATE DATABASE npm_monitor OWNER npm_user;"
sudo -u postgres psql -d npm_monitor -c "GRANT ALL PRIVILEGES ON SCHEMA public TO npm_user;"
```

## 3. Anwendung konfigurieren

Kopiere die Standalone-Vorlage nach `.env` und passe die Werte an:

```bash
cp .env.standalone .env
nano .env
```

**Wichtige Werte in der `.env`:**
* `DB_HOST=localhost`
* `DB_PASSWORD=DEIN_PASSWORT`
* `LOG_DIR=/var/log/npm` (Pfad zu deinen Nginx Logs auf dem Host)
* `NPM_DB_SQLITE_PATH` (Pfad zur NPM `database.sqlite` auf dem Host)

## 4. Lokale Python-Umgebung einrichten

Wir empfehlen `uv` für das Management, aber `pip` funktioniert ebenfalls:

```bash
# Mit uv (empfohlen)
uv sync

# ODER mit pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Daten aus Docker migrieren (Optional)

Falls du deine alten Daten behalten möchtest, nutze das vorbereitete Skript:

1. Trage dein Passwort im Skript ein: `nano scripts/migrate-to-local.sh`
2. Stelle sicher, dass der Docker-Container noch läuft.
3. Führe das Skript aus:
```bash
bash scripts/migrate-to-local.sh
```

## 6. Datenbank-Schema anwenden

Erstelle die Tabellen in der lokalen PostgreSQL Instanz:

```bash
python3 -m alembic upgrade head
```

## 7. Dienste starten

### Manuell via Makefile (zum Testen)
Du kannst die Dienste in separaten Terminals starten:
* `make ui` (Dashboard)
* `make log-worker` (Echtzeit-Sync)
* `make cron-worker` (Hintergrund-Checks)

### Dauerhaft via systemd (Produktion)
Kopiere die Service-Vorlagen und aktiviere sie:

```bash
sudo cp scripts/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Dienste aktivieren und starten
sudo systemctl enable --now npm-ui
sudo systemctl enable --now npm-log-worker
sudo systemctl enable --now npm-cron-worker
sudo systemctl enable --now npm-ai
sudo systemctl enable --now npm-api
```

## 8. Status prüfen

```bash
# Logs einsehen
journalctl -u npm-ui -f
journalctl -u npm-log-worker -f

# Status aller Monitor-Dienste
systemctl status "npm-*"
```
