#!/bin/sh
# Bootstrap installer for Google Antigravity on Linux x64.
#
#   curl -fsSL https://raw.githubusercontent.com/raybird/antigravity-installer/main/install.sh | sudo sh
#
# Downloads install.py and runs it. A system-wide install is selected
# automatically when running as root, otherwise the install is user-local.
#
# Arguments after `-s --` are passed straight through to install.py:
#
#   ... | sh -s -- --check ide app       # report versions, no sudo needed
#   ... | sudo sh -s -- ide              # IDE only
#   ... | sudo sh -s -- --force ide      # reinstall a damaged install
#
# With no arguments both products are installed.
#
# Pin to a tag or commit instead of the moving branch tip:
#
#   ANTIGRAVITY_INSTALLER_REF=v1.0.0 ... | sudo -E sh
set -eu

REPO="${ANTIGRAVITY_INSTALLER_REPO:-raybird/antigravity-installer}"
REF="${ANTIGRAVITY_INSTALLER_REF:-main}"
BASE="${ANTIGRAVITY_INSTALLER_BASE:-https://raw.githubusercontent.com/$REPO/$REF}"
SOURCE="${ANTIGRAVITY_INSTALLER_SOURCE:-$BASE/install.py}"
GUI_SOURCE="${ANTIGRAVITY_INSTALLER_GUI_SOURCE:-$BASE/gui.py}"

die() {
    echo "install.sh: $*" >&2
    exit 1
}

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$1"
    else
        die "need curl or wget to download the installer"
    fi
}

command -v python3 >/dev/null 2>&1 || die "need python3 (3.10 or newer)"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' ||
    die "need Python 3.10 or newer, found $(python3 -V 2>&1)"

# Default to both products so a bare `| sudo sh` does the expected thing.
if [ "$#" -eq 0 ]; then
    set -- ide app
fi

# install.py only copies gui.py if it sits next to it, so fetch it on demand.
wants_gui=0
for arg in "$@"; do
    if [ "$arg" = "--install-gui" ]; then
        wants_gui=1
        break
    fi
done

# Running as root means /opt and /usr/local, which is what sudo implies here.
# An explicit ANTIGRAVITY_INSTALL_MODE always wins.
if [ -z "${ANTIGRAVITY_INSTALL_MODE:-}" ] && [ "$(id -u)" = "0" ]; then
    ANTIGRAVITY_INSTALL_MODE=system
    export ANTIGRAVITY_INSTALL_MODE
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

echo "Fetching $SOURCE"
fetch "$SOURCE" >"$tmp/install.py" || die "could not download $SOURCE"
[ -s "$tmp/install.py" ] || die "downloaded installer is empty"
# Catches a proxy or error page being saved as the installer.
head -n 1 "$tmp/install.py" | grep -q '^#!/usr/bin/env python3$' ||
    die "downloaded file is not install.py"

if [ "$wants_gui" = "1" ]; then
    echo "Fetching $GUI_SOURCE"
    fetch "$GUI_SOURCE" >"$tmp/gui.py" || die "could not download $GUI_SOURCE"
    head -n 1 "$tmp/gui.py" | grep -q '^#!/usr/bin/env python3$' ||
        die "downloaded file is not gui.py"
fi

python3 "$tmp/install.py" "$@"
