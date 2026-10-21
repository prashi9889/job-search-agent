#!/usr/bin/env bash
# One-time setup for macOS / Linux:  bash install.sh [path/to/profile.json]
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || true)
if [ -z "$PY" ]; then
  echo "Python 3 is needed. Install it from https://www.python.org/downloads/ and run this again."; exit 1
fi
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Python 3.11 or newer is needed."; exit 1; }

"$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .
.venv/bin/jobagent init

if [ "${1:-}" != "" ]; then
  .venv/bin/jobagent profile import "$1"
fi

.venv/bin/jobagent schedule install --every 30
echo
echo "Done. The agent now runs every 30 minutes in the background."
echo "Dashboard:  .venv/bin/jobagent serve   then open http://127.0.0.1:8765"
echo "Connect Gmail + Calendar when ready:  .venv/bin/jobagent connect google"
