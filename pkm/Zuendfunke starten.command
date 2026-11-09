#!/bin/bash
# Startet Zündfunke mit Zugriff auf den PKM-Ordner und öffnet die App im Standardbrowser.
cd "$(dirname "$0")" || exit 1
URL="http://localhost:8765"
if curl -s -m 2 "$URL/api/status" | grep -q zuendfunke-pkm; then
  open "$URL"; exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 wurde nicht gefunden. Installiere die Entwicklerwerkzeuge mit: xcode-select --install"
  read -r -p "Enter zum Schließen" _; exit 1
fi
(sleep 1.5; open "$URL") &
python3 server.py
read -r -p "Zündfunke wurde beendet. Enter zum Schließen" _
