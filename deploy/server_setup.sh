#!/bin/bash
# One-time setup on a fresh Debian 12 Google Cloud e2-micro VM. Run as root:  bash server_setup.sh <domain>
# Installs the app in /opt/mealplanner, runs it with waitress under systemd, and puts Caddy (automatic HTTPS)
# in front of it. Safe to run again.
set -euo pipefail
DOMAIN="${1:?usage: server_setup.sh <domain>}"
APP=/opt/mealplanner
REPO=https://github.com/Zakede/MealPlanner.git

# 1 GB of RAM is tight: add swap once
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-venv git caddy sqlite3

id -u mealplanner >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin mealplanner
if [ ! -d "$APP/.git" ]; then
  git clone -q "$REPO" "$APP"
else
  git -C "$APP" pull -q --ff-only
fi
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt" waitress
mkdir -p "$APP/instance"
chown -R mealplanner:mealplanner "$APP"

# settings that live outside the code (the site password hash is added by deploy.py)
touch /etc/mealplanner.env
chmod 600 /etc/mealplanner.env
grep -q '^MEALPLANNER_BEHIND_PROXY=' /etc/mealplanner.env || echo 'MEALPLANNER_BEHIND_PROXY=1' >> /etc/mealplanner.env
grep -q '^TZ=' /etc/mealplanner.env || echo 'TZ=Asia/Tokyo' >> /etc/mealplanner.env

cat > /etc/systemd/system/mealplanner.service <<EOF
[Unit]
Description=Meal Planner
After=network.target

[Service]
User=mealplanner
WorkingDirectory=$APP
EnvironmentFile=/etc/mealplanner.env
ExecStart=$APP/.venv/bin/waitress-serve --host 127.0.0.1 --port 5000 --threads 6 --call mealplanner:create_app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
	encode gzip
	reverse_proxy 127.0.0.1:5000
}
EOF

systemctl daemon-reload
systemctl enable -q mealplanner caddy
systemctl restart mealplanner caddy
echo "ready: https://$DOMAIN"
