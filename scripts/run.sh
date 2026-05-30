#!/usr/bin/env bash

set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

uv run uvicorn src.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload
