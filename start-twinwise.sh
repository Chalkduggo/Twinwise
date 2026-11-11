#!/usr/bin/env bash
# Run Twinwise from source on macOS or Linux (needs Python 3.10+).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Setting up Twinwise for the first time..."
  python3 -m venv .venv && .venv/bin/pip install --quiet --upgrade pip && .venv/bin/pip install --quiet -e .
fi
.venv/bin/python -m twinwise ui
