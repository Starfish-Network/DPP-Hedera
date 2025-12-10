FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN apt-get update && \
    apt-get install -y build-essential git libpq-dev && \
    rm -rf /var/lib/apt/lists/* && \
    pip install hiero-sdk-python py-solc-x python-dotenv && \
    sed -i 's/Optional\[TokenFreezeStatusProto\]/Optional[any]/g' \
    $(python -c "import hiero_sdk_python, os; print(os.path.join(os.path.dirname(hiero_sdk_python.__file__), 'tokens', 'token_relationship.py'))")

CMD ["python", "deploy_compliance_contract.py"]