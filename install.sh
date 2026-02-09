#!/usr/bin/env bash
set -e

echo "[1/7] Installing system packages"
apt update
apt install -y python3 python3-venv python3-pip git sqlite3

echo "[2/7] Creating directories"
mkdir -p /opt/attendance
mkdir -p /var/lib/attendance/faces
mkdir -p /etc/attendance

echo "[3/7] Cloning repository"
git clone https://github.com/stujoubert/PiServer.git /opt/attendance

echo "[4/7] Creating virtualenv"
python3 -m venv /opt/attendance/venv
/opt/attendance/venv/bin/pip install -r /opt/attendance/requirements.txt

echo "[5/7] Creating env file"
cat > /etc/attendance/attendance.env <<EOF
ATT_ENV=prod
ATT_DB=/var/lib/attendance/attendance.db
ATT_PORT=5000
SECRET_KEY=change_me
EOF

echo "[6/7] Installing systemd service"
cp /opt/attendance/attendance.service /etc/systemd/system/attendance.service
systemctl daemon-reload
systemctl enable attendance

echo "[7/7] Starting service"
systemctl start attendance

echo "Attendance installed and running"
