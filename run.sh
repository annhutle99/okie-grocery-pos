#!/bin/bash
# SmartRetail Launcher Script

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "$DIR/venv/bin/python" ]; then
    "$DIR/venv/bin/python" main.py
else
    python3.12 main.py
fi
