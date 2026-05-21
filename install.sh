#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Leadmachine Installer
# Installiert Python (falls noetig), baut Leadmachine.app und legt sie
# wahlweise in /Applications ab.
# ─────────────────────────────────────────────────────────────────────────────
set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Leadmachine"
PYTHON_URL="https://www.python.org/ftp/python/3.12.8/python-3.12.8-macos11.pkg"
PYTHON_PKG="/tmp/python3-installer.pkg"

# ── Farben ───────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"; BLUE="\033[0;34m"; AMBER="\033[0;33m"
RED="\033[0;31m"; BOLD="\033[1m"; NC="\033[0m"

info()  { echo -e "${BLUE}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${AMBER}!${NC} $*"; }
error() { echo -e "${RED}✗ FEHLER:${NC} $*"; exit 1; }
title() { echo -e "\n${BOLD}$*${NC}"; }

# ─────────────────────────────────────────────────────────────────────────────
title "Leadmachine Installer"
echo "────────────────────────────────────"

# ── Schritt 1: Python mit Tk 8.6+ suchen ────────────────────────────────────
title "1 / 4  Python prüfen"
find_python() {
    for p in \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3; do
        [ -x "$p" ] || continue
        if "$p" -c 'import tkinter,sys; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)' 2>/dev/null; then
            echo "$p"; return 0
        fi
    done
    return 1
}

if PY=$(find_python); then
    ok "Python mit Tk 8.6+ gefunden: $PY"
else
    warn "Kein geeignetes Python gefunden. Das macOS-System-Python hat nur Tk 8.5."
    echo ""
    info "Lade Python 3.12.8 herunter (~46 MB) ..."
    curl -# -L -o "$PYTHON_PKG" "$PYTHON_URL" || error "Download fehlgeschlagen."
    ok "Download abgeschlossen."
    echo ""
    info "Installiere Python (benötigt Admin-Passwort) ..."
    sudo installer -pkg "$PYTHON_PKG" -target / || error "Python-Installation fehlgeschlagen."
    rm -f "$PYTHON_PKG"
    PY=$(find_python) || error "Python nach Installation nicht gefunden. Bitte manuell prüfen."
    ok "Python installiert: $PY"
fi

# ── Schritt 2: Abhängigkeiten ────────────────────────────────────────────────
title "2 / 4  Abhängigkeiten installieren"
info "customtkinter + PyInstaller ..."
"$PY" -m pip install --quiet --upgrade customtkinter pyinstaller
ok "Abhängigkeiten installiert."

# ── Schritt 3: App bauen ─────────────────────────────────────────────────────
title "3 / 4  App bauen"
info "Starte Build (dauert ~60 Sekunden) ..."

BUILD=$(mktemp -d)
cp "$REPO_DIR/leadmachine.py" "$BUILD/"
(
    cd "$BUILD"
    "$PY" -m PyInstaller \
        --windowed --onedir --name "$APP_NAME" --noconfirm \
        --collect-all customtkinter --collect-all darkdetect \
        --osx-bundle-identifier de.leadmachine.app \
        leadmachine.py 2>&1 | grep -E "Building|completed|ERROR" | tail -4
)

APP_SRC="$BUILD/dist/$APP_NAME.app"
info "Signiere App ..."
find "$APP_SRC" -name "._*" -delete 2>/dev/null || true
find "$APP_SRC" -name ".DS_Store" -delete 2>/dev/null || true
xattr -cr "$APP_SRC" 2>/dev/null || true
codesign --remove-signature "$APP_SRC" 2>/dev/null || true
codesign --force --deep --sign - "$APP_SRC" 2>/dev/null && ok "Signiert." || warn "Signierung nicht vollständig (App läuft trotzdem)."

ok "Build abgeschlossen."

# ── Schritt 4: Installieren ──────────────────────────────────────────────────
title "4 / 4  App installieren"
echo ""
echo "  [1]  /Applications/Leadmachine.app  ← für alle Benutzer, im Launchpad sichtbar"
echo "  [2]  Hier im Repo-Ordner            ← nur für dich, kein Launchpad-Eintrag"
echo ""
read -r -p "  Installationsziel [1/2]: " choice

case "$choice" in
    2)
        DEST="$REPO_DIR/$APP_NAME.app"
        rm -rf "$DEST"
        ditto "$APP_SRC" "$DEST"
        xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
        ok "Installiert: $DEST"
        ;;
    *)
        DEST="/Applications/$APP_NAME.app"
        rm -rf "$DEST"
        ditto "$APP_SRC" "$DEST"
        xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
        ok "Installiert: $DEST"
        ;;
esac

rm -rf "$BUILD"

echo ""
echo -e "${GREEN}${BOLD}────────────────────────────────────${NC}"
echo -e "${GREEN}${BOLD}  Leadmachine erfolgreich installiert${NC}"
echo -e "${GREEN}${BOLD}────────────────────────────────────${NC}"
echo ""
echo "  Starten: Doppelklick auf $APP_NAME.app"
echo ""
echo "  Beim ersten Start fragt macOS nach Ordner-Zugriff"
echo "  (für leads.json) → \"Erlauben\" klicken."
echo ""

# App direkt öffnen?
read -r -p "  Jetzt öffnen? [j/N]: " open_now
if [[ "$open_now" =~ ^[jJyY] ]]; then
    open "$DEST"
fi
