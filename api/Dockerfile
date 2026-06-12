# Use official lightweight Python image
FROM python:3.12-slim

WORKDIR /app

# system deps for psycopg2 and git (for SDK if needed)
RUN apt-get update && apt-get install -y build-essential libpq-dev git && rm -rf /var/lib/apt/lists/*

# uv installs dependencies from the frozen lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install deps first so this layer is cached unless pyproject.toml / uv.lock change.
# The dev group (pytest) is included so the docker-compose `integration-tests`
# service can run pytest inside this image, as it did when deps came from
# requirements.txt.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# Put the resolved venv on PATH so `uvicorn` / `python` / `pytest` resolve directly.
ENV PATH="/app/.venv/bin:$PATH"

# Temporary fix for protobuf compatibility issue with hiero_sdk_python
RUN sed -i 's/Optional\[TokenFreezeStatusProto\]/Optional[any]/g' \
    $(python -c "import hiero_sdk_python, os; print(os.path.join(os.path.dirname(hiero_sdk_python.__file__), 'tokens', 'token_relationship.py'))")

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
