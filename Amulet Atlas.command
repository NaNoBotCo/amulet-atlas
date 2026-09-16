#!/bin/bash
# Amulet Atlas — numbered menu. Double-click me.
cd "$(dirname "$0")"
PORT=8798
while true; do
  clear
  cat <<'MENU'
================================================================
  AMULET ATLAS — amulets, charms and talismans worldwide
================================================================
  1  Open the site               (build/site in your browser)
  2  Rebuild everything          (validate → build → cards → site)
  3  Validate the records only
  4  Serve it                    (http://127.0.0.1:8798)
  5  Draw the missing share cards
  6  Refresh the country outlines (Natural Earth)
  7  Refresh the Wikipedia corpus
  8  Publish into docs/          (what GitHub Pages serves)
  9  Run the tests
  0  Quit
================================================================
MENU
  read -r -p "  Pick a number: " n
  case "$n" in
    1) [ -f build/site/index.html ] && open build/site/index.html || echo "  Nothing built yet — pick 2 first."; read -r -p "  Enter to go on… " _ ;;
    2) python3 tools/validate.py && python3 tools/build.py && python3 tools/cards.py && python3 tools/site.py; read -r -p "  Enter to go on… " _ ;;
    3) python3 tools/validate.py; read -r -p "  Enter to go on… " _ ;;
    4) echo "  Ctrl-C to stop."; python3 tools/serve.py $PORT ;;
    5) python3 tools/cards.py; read -r -p "  Enter to go on… " _ ;;
    6) python3 tools/fetch_geo.py; read -r -p "  Enter to go on… " _ ;;
    7) read -r -p "  Folder to write the corpus into: " d; python3 tools/fetch_wiki.py "$d"; read -r -p "  Enter to go on… " _ ;;
    8) ./publish.sh; read -r -p "  Enter to go on… " _ ;;
    9) python3 -m unittest discover -s tests; read -r -p "  Enter to go on… " _ ;;
    0) exit 0 ;;
    *) ;;
  esac
done
