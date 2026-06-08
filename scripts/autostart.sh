#!/usr/bin/env bash
# autostart.sh — Install a systemd service so the BackDeezUp Docker Compose
# stack starts automatically when Debian WSL boots on WINWEB01.
#
# Run as root (or with sudo):
#   sudo bash scripts/autostart.sh
#
# ── IMPORTANT: WSL2 does NOT auto-start on VM boot by itself ──────────────
# This script only installs the systemd unit. To make it run on Windows
# startup you also need one of the approaches described at the bottom.
# The companion file scripts/windows-autostart.bat handles the Windows side.
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

SERVICE_FILE="/etc/systemd/system/backdeezup.service"
PROJECT_DIR="/home/saitama/repos/github/devadalberto/backdeezup"
SERVICE_USER="saitama"

echo ""
echo "=== BackDeezUp autostart installer ==="
echo "Installing systemd service: $SERVICE_FILE"
echo ""

# ── Write the unit file ───────────────────────────────────────────────────
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=BackDeezUp Docker Compose Stack
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=${SERVICE_USER}

[Install]
WantedBy=multi-user.target
EOF

echo "Service file written to $SERVICE_FILE"

# ── Enable the service ────────────────────────────────────────────────────
systemctl daemon-reload
systemctl enable backdeezup.service

echo ""
echo "=== Done ==="
echo "The backdeezup.service systemd unit is now ENABLED."
echo "It will start automatically the next time Debian WSL boots with systemd."
echo ""
echo "To start it right now:  sudo systemctl start backdeezup.service"
echo "To check its status:    sudo systemctl status backdeezup.service"
echo "To stop it:             sudo systemctl stop backdeezup.service"
echo "To disable autostart:   sudo systemctl disable backdeezup.service"
echo ""

# ── WSL2 + Windows startup note ───────────────────────────────────────────
cat <<'NOTE'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WSL2 AUTO-START ON VM BOOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WSL2 itself does not launch automatically when Windows starts. To run the
stack on WINWEB01 reboot you need to trigger WSL from the Windows side.

Option A — Windows Startup Folder (recommended for WINWEB01)
  Copy (or shortcut) scripts/windows-autostart.bat into:
    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
  It runs:
    wsl -d Debian -u saitama -- bash -c "cd ~/repos/github/devadalberto/backdeezup && docker compose up -d"

Option B — Windows Task Scheduler
  Create a task triggered At startup, run as SYSTEM (or Administrator):
    Program: wsl.exe
    Arguments: -d Debian -u saitama -- bash -c "cd ~/repos/github/devadalberto/backdeezup && docker compose up -d"

Option C — Registry Run key (HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run)
  Add a string value:
    Name:  BackDeezUp
    Data:  wsl -d Debian -u saitama -- bash -c "cd ~/repos/github/devadalberto/backdeezup && docker compose up -d"

The companion file scripts/windows-autostart.bat (for Option A) is already
present in this repository. Copy it to your Startup folder.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTE
