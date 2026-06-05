#!/usr/bin/env bash
# One-command setup for the DPP-Hedera API. Installs uv (if missing) + Python
# 3.12, syncs dependencies from uv.lock, and seeds a local .env.dev. Re-runnable.
#
# After this, run the app with:   ./run.sh        (or: uv run uvicorn app.main:app --reload)
# Run unit tests with:            uv run --locked pytest app/tests/unit -m "not integration"
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

# uv manages the virtualenv and the Python 3.12 toolchain (per .python-version).
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing via the official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "Syncing dependencies with uv..."
uv sync

if [ ! -f ".env.dev" ]; then
    cp .env.example .env.dev
    echo "Created .env.dev from .env.example — fill in OPERATOR_ID / OPERATOR_KEY / TOPIC_ID / JWT_SECRET before running."
fi

echo ""
echo "Setup complete. Start the API with ./run.sh"
