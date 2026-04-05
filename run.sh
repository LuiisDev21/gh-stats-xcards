#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
PORT="${PORT:-8000}"

uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --reload
