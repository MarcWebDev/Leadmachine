#!/bin/bash
# Baut Leadmachine.app (eigenstaendiges macOS-App-Bundle).
set -e
cd "$(dirname "$0")"

APP_NAME="Leadmachine"
SRC="leadmachine.py"

# ── Python mit Tk 8.6+ suchen ────────────────────────────────────────────────
# customtkinter rendert nicht auf Tk 8.5 (macOS-System-Python). Tk 8.6 noetig.
find_python() {
    for p in \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        python3; do
        command -v "$p" >/dev/null 2>&1 || continue
        if "$p" -c 'import tkinter,sys; sys.exit(0 if tkinter.TkVersion>=8.6 else 1)' 2>/dev/null; then
            echo "$p"
            return 0
        fi
    done
    return 1
}

PY=$(find_python) || {
    echo "FEHLER: Kein Python mit Tk 8.6+ gefunden."
    echo "Installiere python.org Python 3.12+: https://www.python.org/downloads/macos/"
    exit 1
}
echo "Python: $PY"

# ── Abhaengigkeiten ──────────────────────────────────────────────────────────
"$PY" -m pip install --quiet --upgrade customtkinter pyinstaller

# ── Build in temporaerem Verzeichnis ─────────────────────────────────────────
# Cloud-Sync-Ordner (iCloud/OneDrive) stempeln xattrs auf Verzeichnisse,
# wodurch codesign fehlschlaegt. Daher ausserhalb bauen.
BUILD=$(mktemp -d)
cp "$SRC" "$BUILD/"
(
    cd "$BUILD"
    "$PY" -m PyInstaller \
        --windowed --onedir --name "$APP_NAME" --noconfirm \
        --collect-all customtkinter --collect-all darkdetect \
        --osx-bundle-identifier de.leadmachine.app \
        "$SRC"
)

APP="$BUILD/dist/$APP_NAME.app"

# ── Detritus entfernen + ad-hoc signieren ────────────────────────────────────
find "$APP" -name "._*" -delete 2>/dev/null || true
find "$APP" -name ".DS_Store" -delete 2>/dev/null || true
xattr -cr "$APP" 2>/dev/null || true
codesign --remove-signature "$APP" 2>/dev/null || true
codesign --force --deep --sign - "$APP"

# ── Ergebnis zurueckkopieren ─────────────────────────────────────────────────
rm -rf "./$APP_NAME.app"
ditto "$APP" "./$APP_NAME.app"
xattr -dr com.apple.quarantine "./$APP_NAME.app" 2>/dev/null || true
rm -rf "$BUILD"

echo ""
echo "Fertig: ./$APP_NAME.app  (Doppelklick zum Starten)"
