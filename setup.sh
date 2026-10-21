#!/bin/zsh
set -euo pipefail

cd "${0:A:h}"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "Setup complete. Edit .env, then run:"
echo "  .venv/bin/python monitor.py --test-email"
echo "  .venv/bin/python monitor.py --once"
echo "  .venv/bin/python monitor.py"
