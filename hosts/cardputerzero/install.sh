#!/bin/sh
# Put Ace Commander on the CardputerZero's launcher (APPLaunch). Run with sudo from
# the repo copy on the device:  sudo sh ~/ace_commander/hosts/cardputerzero/install.sh
# The launcher reads entries only from /usr/share/APPLaunch (root's), so this needs sudo.
set -e
HERE=$(dirname "$(readlink -f "$0")")
USER_HOME=$(getent passwd "${SUDO_USER:-pi}" | cut -d: -f6)
APPS=/usr/share/APPLaunch/applications
IMAGES=/usr/share/APPLaunch/share/images
[ -d "$APPS" ] || { echo "no $APPS: is APPLaunch installed?"; exit 1; }
mkdir -p "$IMAGES"
cp "$HERE/icon.png" "$IMAGES/ace_commander.png"
cat > "$APPS/ace_commander.desktop" <<DESK
[Desktop Entry]
Name=Ace Commander
Exec=$HERE/ace-commander.sh
Terminal=false
Icon=share/images/ace_commander.png
Type=Application
DESK
chmod 644 "$APPS/ace_commander.desktop" "$IMAGES/ace_commander.png"
echo "installed: $APPS/ace_commander.desktop -> $HERE/ace-commander.sh"
echo "(restart the launcher to see it: systemctl --user restart APPLaunch, as ${SUDO_USER:-pi})"
