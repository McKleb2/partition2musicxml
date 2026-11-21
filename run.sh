#!/usr/bin/env bash
# Lance l'application web (http://127.0.0.1:8000) ou, avec des arguments, l'outil en ligne de commande.
#   ./run.sh                      → application web
#   ./run.sh partition.pdf -o out → conversion directe
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$APP_DIR/.env" ]; then set -a; . "$APP_DIR/.env"; set +a; fi
cd "$APP_DIR"
if [ $# -gt 0 ]; then exec .venv/bin/python cli.py "$@"; else exec .venv/bin/python server.py; fi
