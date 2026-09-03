#!/usr/bin/env bash
# Permanently disable the Kali seat0 screen lock/blank so GUI automation
# (capture.sh burp, xdotool driving Burp) never has synthetic input routed to
# a locker instead of the app. Idempotent; re-run after a box rebuild.
# See setup/burp/README.md and the "Burp GUI automation" section of
# docs/setup.md for the failure mode this fixes.
set -euo pipefail

DISPLAY="${DISPLAY:-:0}"
export DISPLAY

echo "Disabling xfce4-screensaver saver/lock..."
xfconf-query -c xfce4-screensaver -p /saver/enabled -s false 2>/dev/null || true
xfconf-query -c xfce4-screensaver -p /lock/enabled -s false 2>/dev/null || true

echo "Removing xfce4-screensaver autostart..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/xfce4-screensaver.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Xfce4 Screensaver
Hidden=true
EOF

echo "Disabling DPMS/blanking..."
xset s off
xset s noblank
xset -dpms

echo "Persisting DPMS/blanking-off across logins (~/.xprofile)..."
XPROFILE="$HOME/.xprofile"
touch "$XPROFILE"
grep -qxF 'xset s off' "$XPROFILE" || echo 'xset s off' >> "$XPROFILE"
grep -qxF 'xset s noblank' "$XPROFILE" || echo 'xset s noblank' >> "$XPROFILE"
grep -qxF 'xset -dpms' "$XPROFILE" || echo 'xset -dpms' >> "$XPROFILE"

echo "Done. Seat0 lock/blank disabled (survives logout via ~/.xprofile); re-run after a box rebuild."
