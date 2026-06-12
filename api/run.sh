#!/usr/bin/env bash
# Run the DPP-Hedera API locally with auto-reload. Reads config from .env.dev
# (loaded by the app via pydantic-settings). Fails fast if deps are out of step
# with uv.lock — run ./setup.sh to reconcile.
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed. Run ./setup.sh" >&2
    exit 1
fi
if ! uv lock --check >/dev/null 2>&1; then
    echo "Error: pyproject.toml and uv.lock disagree. Run ./setup.sh, then commit uv.lock." >&2
    exit 1
fi

exec uv run --locked uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
