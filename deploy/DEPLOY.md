# Deploying to Google Cloud Compute Engine (Ubuntu + NGINX + uWSGI)

Request flow: **Internet → GCP firewall (port 80) → NGINX → uWSGI socket → Flask app**

## Files in this bundle

| File | Purpose | Installed to |
|---|---|---|
| `../wsgi.py` | uWSGI entry point that exposes the Flask `app` | stays in app folder |
| `uwsgi.ini` | uWSGI process/socket configuration | read in place |
| `hdb-resale.service` | systemd unit that runs uWSGI on boot | `/etc/systemd/system/` |
| `nginx-hdb-resale.conf` | NGINX site that proxies to the uWSGI socket | `/etc/nginx/sites-available/` |
| `setup.sh` | One-shot provisioning script that does all of the above | run once with sudo |

All configs assume the project lives at `/srv/hdb-resale-app`. If you use a
different path, update `uwsgi.ini`, `hdb-resale.service` and `setup.sh`.

## Dependencies

**System packages (installed by setup.sh):**
`python3`, `python3-venv`, `python3-pip`, `python3-dev`, `build-essential` (pip
compiles uWSGI from C source), `nginx`

**Python packages (installed by setup.sh into a venv):**
`flask`, `requests`, `pandas`, `SQLAlchemy` (from `requirements.txt`) plus
`uwsgi`. uWSGI is deliberately not in `requirements.txt` because it does not
build on Windows for local development.

## Step 1 — Create the instance

Console: Compute Engine → Create instance
- Machine type: `e2-small` (2 GB RAM) or larger. Avoid `e2-micro` — the pandas
  build of the full dataset can exhaust 1 GB of RAM.
- Boot disk: Ubuntu 24.04 LTS (or 22.04 LTS), default 10 GB is plenty.
- Firewall: tick **Allow HTTP traffic** (opens port 80).

Or with the gcloud CLI:

```
gcloud compute instances create hdb-resale --machine-type=e2-small --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud --tags=http-server
gcloud compute firewall-rules create default-allow-http --allow=tcp:80 --target-tags=http-server
```

(The firewall rule may already exist in your project; creating it again just errors harmlessly.)

## Step 2 — Copy the project to the instance

From this project's parent directory on your machine:

```
gcloud compute scp --recurse hdb-resale-app hdb-resale:/tmp/hdb-resale-app
```

Then on the instance (`gcloud compute ssh hdb-resale`):

```
sudo mv /tmp/hdb-resale-app /srv/hdb-resale-app
sudo rm -rf /srv/hdb-resale-app/venv /srv/hdb-resale-app/__pycache__
```

(The Windows `venv` is useless on Linux; setup.sh builds a fresh one.)

Note on the database: if you copy `hdb_resale.db` along with the code, the
server keeps your current (trimmed, 2021+) data and skips the download.
Delete it before copying if you want the server to fetch the full dataset
from data.gov.sg instead.

## Step 3 — Provision

On the instance:

```
sudo bash /srv/hdb-resale-app/deploy/setup.sh
```

This installs packages, builds the venv, ensures the database exists, then
starts and enables the `hdb-resale` systemd service and the NGINX site.

If bash complains about `\r` or "bad interpreter", the file picked up Windows
line endings in transit — fix with `sudo sed -i 's/\r$//' /srv/hdb-resale-app/deploy/setup.sh`
and rerun.

## Step 4 — Verify

```
systemctl status hdb-resale --no-pager
curl -s http://localhost | head -n 5
```

Then open `http://<EXTERNAL_IP>` in a browser (external IP shown in the
console or via `gcloud compute instances describe hdb-resale --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`).

## Operations

- App logs: `journalctl -u hdb-resale -f`
- NGINX logs: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- Restart after a code change: `sudo systemctl restart hdb-resale`
- Refresh the dataset: `cd /srv/hdb-resale-app && sudo -u www-data ./venv/bin/python dataloader.py && sudo systemctl restart hdb-resale`

## Security notes

- Only port 80 (HTTP) is exposed; traffic is unencrypted. For HTTPS, point a
  domain at the external IP and run certbot (`sudo apt install certbot
  python3-certbot-nginx && sudo certbot --nginx`).
- The app is read-only (GET + SQL via bound parameters), but it is still a
  public endpoint — keep the instance patched (`sudo apt upgrade`).
- uWSGI runs as the unprivileged `www-data` user, not root.
