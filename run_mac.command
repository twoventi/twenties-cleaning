#!/bin/bash
# Avvio da codice sorgente su macOS (per sviluppatori). Gli utenti scaricano il .dmg dalle Releases.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installalo da https://www.python.org/downloads/macos/ e riprova."
  read -n 1 -s -r -p "Premi un tasto per chiudere..."; exit 1
fi
python3 -m pip install -r requirements.txt || echo "pywebview non installato: se la finestra non si apre, uso il browser."
python3 src/twenties_cleaning.py
