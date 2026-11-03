#!/usr/bin/env bash
# Run with sudo. Source files live beside this script in ps/ (upload staging),
# or in ../src/ps/ when the entire reproduction package was copied onto Linux.
set -euo pipefail
if [ "$#" -ne 5 ]; then
  echo "Usage: sudo bash install_board.sh /home/USER/ore USER /dev/video0 8000 /usr/bin/python3"
  exit 2
fi
target=$1
account=$2
device=$3
port=$4
python_bin=$5
[[ $EUID -eq 0 ]] || { echo 'Run this installer with sudo.'; exit 2; }
[[ "$account" =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 2
for path in "$target" "$device" "$python_bin"; do
  [[ "$path" =~ ^/[A-Za-z0-9_./-]+$ && "$path" != *'/../'* && "$path" != */.. && "$path" != *'//'* ]] || exit 2
done
[[ "$target" != / && "$target" != /home && "$target" != /opt && "$target" != /usr && "$target" != /tmp ]] || exit 2
[[ "$device" == /dev/* && "$port" =~ ^[0-9]+$ && "$port" -ge 1024 && "$port" -le 65535 ]] || exit 2
id "$account" >/dev/null
getent group video >/dev/null || { echo 'Missing video group; install the board camera driver first.'; exit 1; }
"$python_bin" -c 'import sys, cv2, numpy; assert sys.version_info >= (3, 7); print("Board dependencies:", cv2.__version__, numpy.__version__)'
command -v systemctl >/dev/null
command -v systemd-analyze >/dev/null
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -d "$source_dir/ps" ]]; then
  source_dir="$source_dir/ps"
else
  source_dir=$(cd -- "$source_dir/../src/ps" && pwd)
fi
[[ "$source_dir" != "$target" && ! -L "$target" ]] || { echo 'Use a separate non-symlink installation directory.'; exit 2; }
"$python_bin" -m compileall -q "$source_dir"
unit=/etc/systemd/system/ore-vision.service
backup="${target}.backup.$(date +%Y%m%d_%H%M%S).$$"
mkdir -m 755 -p "$backup"
if [[ -d "$target" ]]; then cp -a "$target" "$backup/app"; fi
if [[ -f "$unit" ]]; then cp -p "$unit" "$backup/ore-vision.service"; fi
echo "Backup: $backup"
# Fail before stopping the running service if existing user settings are invalid.
if [[ -f "$target/settings.json" ]]; then
  PYTHONPATH="$source_dir" "$python_bin" -c 'import json,sys; from app_ps import validate; validate(json.load(open(sys.argv[1])))' "$target/settings.json"
fi
group=$(id -gn "$account")
staged_unit="$backup/new-ore-vision.service"
cat > "$staged_unit" <<UNIT
[Unit]
Description=B220 direct USB camera multi-object ore demonstration
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$account
Group=$group
SupplementaryGroups=video
WorkingDirectory=$target
Environment=PYTHONUNBUFFERED=1
ExecStart=$python_bin -u $target/app_ps.py --device $device --port $port
Restart=on-failure
RestartSec=3
StandardOutput=journal+console
StandardError=journal
SyslogIdentifier=ore-vision

[Install]
WantedBy=multi-user.target
UNIT
systemd-analyze verify "$staged_unit"
if systemctl is-active --quiet ore-vision.service; then systemctl stop ore-vision.service; fi
trap 'echo "Install did not finish. Backup retained at: $backup. See docs/troubleshooting.md."' ERR
mkdir -p "$target/badges"
for file in app_ps.py color_labels.py multi_tracking.py multi_vision.py specimen_catalog.py index.html; do
  install -m 644 "$source_dir/$file" "$target/$file"
done
install -m 644 "$source_dir"/badges/*.png "$target/badges/"
if [[ ! -f "$target/settings.json" ]]; then install -m 644 "$source_dir/settings.json" "$target/settings.json"; fi
# Only this dedicated application directory changes ownership.
chown -R "$account:$group" "$target"
install -m 644 "$staged_unit" "$unit"
systemctl daemon-reload
systemctl enable ore-vision.service
systemctl restart ore-vision.service
sleep 2
systemctl is-enabled ore-vision.service
systemctl is-active ore-vision.service
echo "Installed. Camera: $device; HTTP port: $port; app: $target"
echo 'View logs: journalctl -u ore-vision -n 30 --no-pager'
echo 'On images whose Linux console routes to UART, ORE JSON also appears on that UART.'
