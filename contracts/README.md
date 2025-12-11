# How to deploy the contract

To deploy the contract, follow these steps:

```bash
docker build -t contract-deployer .
docker run contract-deployer
```

This will build the Docker image and run the deployment script contained within it. Make sure you have Docker installed and running on your machine before executing these commands.

The deployment script will handle all necessary steps to deploy the contract to the specified blockchain network. Ensure you have the required environment variables set for authentication and network configuration before running the Docker container.

Copy the contract id from the logs once the deployment is complete for future use.