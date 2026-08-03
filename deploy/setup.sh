#!/usr/bin/env bash
# Provision a barebones Ubuntu GCE instance for the HDB resale Flask app.
# Prerequisite: the project has been copied to /srv/hdb-resale-app (see deploy/DEPLOY.md).
# Run as: sudo bash /srv/hdb-resale-app/deploy/setup.sh
set -euo pipefail

APP_DIR=/srv/hdb-resale-app

if [ ! -f "$APP_DIR/app.py" ]; then
    echo "ERROR: project not found at $APP_DIR - copy it there first." >&2
    exit 1
fi

echo "==> Installing system packages ..."
apt-get update
# build-essential + python3-dev are needed because pip compiles uWSGI from source
apt-get install -y python3 python3-venv python3-pip python3-dev build-essential nginx

echo "==> Creating virtualenv and installing Python packages ..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" uwsgi

# Build the SQLite database once, up front. If you copied hdb_resale.db along
# with the code this step is skipped and your existing (e.g. trimmed) data is kept.
if [ ! -f "$APP_DIR/hdb_resale.db" ]; then
    echo "==> No hdb_resale.db found - downloading dataset from data.gov.sg ..."
    (cd "$APP_DIR" && ./venv/bin/python dataloader.py)
fi

echo "==> Setting ownership to www-data ..."
chown -R www-data:www-data "$APP_DIR"

echo "==> Installing systemd service ..."
cp "$APP_DIR/deploy/hdb-resale.service" /etc/systemd/system/hdb-resale.service
systemctl daemon-reload
systemctl enable --now hdb-resale

echo "==> Installing NGINX site ..."
cp "$APP_DIR/deploy/nginx-hdb-resale.conf" /etc/nginx/sites-available/hdb-resale
ln -sf /etc/nginx/sites-available/hdb-resale /etc/nginx/sites-enabled/hdb-resale
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Done. Check status with:"
echo "    systemctl status hdb-resale"
echo "    curl -s http://localhost | head -n 5"
