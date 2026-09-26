# Chatbot — Stage 7

Streamlit and FastAPI run on the existing Azure VM with ChromaDB. PostgreSQL stores chat metadata and Azure Blob Storage stores chat JSON and PDF files.

The model provider remains **OpenRouter** (`openrouter/free`), with the existing `nvidia/nemotron-3-embed-1b:free` embedding model. Stage 7 changes secret storage and deployment, not the provider or models.

## Key Vault

Terraform creates `shahad-chatbot-kv`, enables the existing VM's system-assigned managed identity, and grants it `Key Vault Secrets User`. The test vault is separate.

The backend reads these secrets at startup:

```text
PROJ-DB-NAME
PROJ-DB-USER
PROJ-DB-PASSWORD
PROJ-DB-HOST
PROJ-DB-PORT
PROJ-OPENROUTER-API-KEY
PROJ-AZURE-STORAGE-SAS-URL
PROJ-AZURE-STORAGE-CONTAINER
PROJ-CHROMADB-HOST
PROJ-CHROMADB-PORT
```

`PROJ-OPENROUTER-API-KEY` replaces the assignment's OpenAI secret because this project uses OpenRouter. Secret values are entered outside Terraform and are not committed to Git.

The VM's `.env` contains only:

```dotenv
KEY_VAULT_NAME=shahad-chatbot-kv
DOCKERHUB_NAMESPACE=shahad555
```

Run Terraform from `terraform/` with `terraform.tfvars` based on the example, then `terraform init`, `terraform plan`, and `terraform apply`. Existing database and storage resources are already imported. The VM is updated in place.

## Deployment

GitHub Actions builds public Docker Hub images `shahad555/chatbot-backend` and `shahad555/chatbot-frontend`, tagged with the commit SHA and `latest`. It invokes `update_app.sh` on `chatbot-vm` through Azure CLI. The VM pulls the private repository using its read-only SSH deploy key and runs the images for that exact commit.

Repository Actions secrets:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
AZURE_CREDENTIALS
RESOURCE_GROUP_NAME
VM_NAME
```

Application directory: `/home/azureuser/chatbot-project-CloudComputing`.

The Compose project name and Chroma volume remain `stage3_azure` and `stage3_azure_chroma_azure_data` to preserve existing data.

For an initial manual image deployment, use `docker compose up -d --build --wait`. Normal updates run through GitHub Actions. `stage7_permissions.sql` contains the assignment's database grants and must run as the database administrator in `appdb`.
