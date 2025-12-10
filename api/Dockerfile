# Use official lightweight Python image
FROM python:3.12-slim

WORKDIR /app

# system deps for psycopg2 and git (for SDK if needed)
RUN apt-get update && apt-get install -y build-essential libpq-dev git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Temporary fix for protobuf compatibility issue with hiero_sdk_python
RUN sed -i 's/Optional\[TokenFreezeStatusProto\]/Optional[any]/g' \
    $(python -c "import hiero_sdk_python, os; print(os.path.join(os.path.dirname(hiero_sdk_python.__file__), 'tokens', 'token_relationship.py'))")

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
