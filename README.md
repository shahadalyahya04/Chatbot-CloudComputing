# Cloud Chatbot

## 1. Project Summary

Cloud Chatbot is a web application for AI conversations and questions about PDF documents. Users can upload a PDF, ask questions about its contents, and save or reopen conversations.

The application runs on an Azure Linux virtual machine using Docker Compose:

| Component | Purpose |
| --- | --- |
| Streamlit | Web interface |
| FastAPI | Chat, document processing, and storage API |
| OpenRouter | Chat responses and text embeddings |
| ChromaDB | Vector search over uploaded documents |
| Azure PostgreSQL | Conversation metadata |
| Azure Blob Storage | PDF files and conversation messages |
| Azure Key Vault | Application secrets |

Terraform manages the cloud resources defined in this repository. GitHub Actions builds the application images, publishes them to Docker Hub, and deploys them to the VM.

### Application Preview

**Welcome screen** — Create a conversation, attach a PDF, or reopen a saved chat from the sidebar.

<img width="957" height="500" alt="Screenshot 2026-10-04 204342" src="https://github.com/user-attachments/assets/643297d0-9e13-45ef-ac85-21aaec9b0090" />

**AI conversation** — Ask questions and read responses directly in the chat interface.

<img width="954" height="499" alt="image" src="https://github.com/user-attachments/assets/c9fde7c5-ed1c-48e2-b469-4ae493b3db4c" />


**PDF summarization** — Upload a document and ask the chatbot to summarize its contents.

<img width="955" height="503" alt="Screenshot 2026-10-04 204654" src="https://github.com/user-attachments/assets/51e6fb27-6ab8-48cd-a1f3-d32b6564a09a" />

## 2. Requirements

**To deploy and run the application:**

- An Azure subscription with a Linux VM, PostgreSQL Flexible Server, and a Blob Storage account and container.
- An OpenRouter account and API key.
- Git, Docker Engine, and the Docker Compose plugin on the VM.
- Azure CLI and Terraform for provisioning and managing infrastructure. Terraform version constraints are defined in `terraform/providers.tf`.
- A PostgreSQL client, such as DBeaver, for database setup.
- GitHub and Docker Hub accounts for automated deployment.

**For Python development outside Docker:** Python 3.12 and the packages in `requirements.txt`. These include Streamlit, FastAPI, Uvicorn, LangChain, ChromaDB, PostgreSQL and Azure clients, and PDF processing libraries. Docker installs Python and these packages during the image build.

## 3. Installation

### Get the source code

Clone the repository using a GitHub account with access to it:

```bash
git clone https://github.com/shahadalyahya04/chatbot-project-CloudComputing.git
cd chatbot-project-CloudComputing
```

### Configure the Azure resources

The supplied Terraform configuration targets an existing deployment. It manages PostgreSQL, Blob Storage, Key Vault, and the existing VM's identity and vault access. It does not provision a new VM or network.

Before using a different Azure environment, update the resource names and import IDs in `terraform/` to match that environment. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, fill in its values, and run these commands from a machine with Azure CLI and Terraform installed:

```bash
az login
cd terraform
terraform init
terraform plan
terraform apply
cd ..
```

Next, complete the database and storage setup:

1. Create a PostgreSQL database named `appdb` if it does not already exist.
2. Allow the VM's outbound IP and your database client's IP through the PostgreSQL firewall.
3. Connect to `appdb` as the database administrator and run `setup_appdb.sql`. This creates the application user and the `advanced_chats` table and grants their required permissions.
4. Create a Blob Storage container and generate a Blob service SAS URL with permissions to read, list, write, and delete the application's files. For an account SAS, select all three allowed resource types.
5. Add the Key Vault secrets listed in section 5.

### Prepare the application on the VM

Place the repository on the VM, then create its environment file from the example:

```bash
cp .env.example .env
```

Set the vault name and Docker Hub namespace as described in section 5. The VM must have a managed identity with the **Key Vault Secrets User** role on the application's vault; the Terraform configuration sets up this access.

If you are developing Python code outside Docker, install the dependencies in a virtual environment. These Linux commands install the packages only; the database, storage, vector service, and Azure authentication must also be configured:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Run the Project

From the repository directory on the configured Azure VM, build and start all three services:

```bash
docker compose up -d --build --wait
docker compose ps
```

Open `http://<VM_PUBLIC_IP>:8501` in a browser. Allow inbound TCP port `8501` in the VM's network security group. The interface supports creating conversations, uploading PDFs, and reopening saved chats.

For a deployment with images already published to Docker Hub, use:

```bash
docker compose pull backend chatbot
docker compose up -d --no-build --wait
```

Check the backend's health from inside the VM:

```bash
curl --fail http://127.0.0.1:5000/health/
```

The backend is available to the frontend over the Compose network; its host port is restricted to the VM's loopback interface. ChromaDB stores its data in a persistent Docker volume. Changing the Compose project or volume name will select a different data volume.

## 5. API Keys & Environment Variables

### Application configuration

Set these values in the VM's `.env` file:

```dotenv
KEY_VAULT_NAME=your-key-vault-name
DOCKERHUB_NAMESPACE=your-dockerhub-username
```

Store the following secrets in that Key Vault:

| Secret name | Required value |
| --- | --- |
| `PROJ-DB-NAME` | `appdb` |
| `PROJ-DB-USER` | `appuser` |
| `PROJ-DB-PASSWORD` | Password assigned to `appuser` |
| `PROJ-DB-HOST` | PostgreSQL server hostname |
| `PROJ-DB-PORT` | `5432` |
| `PROJ-OPENROUTER-API-KEY` | OpenRouter API key |
| `PROJ-AZURE-STORAGE-SAS-URL` | Blob service SAS URL |
| `PROJ-AZURE-STORAGE-CONTAINER` | Name of the storage container |
| `PROJ-CHROMADB-HOST` | `chromadb` for the supplied Compose configuration |
| `PROJ-CHROMADB-PORT` | `8000` |

The backend reads these values at startup through `DefaultAzureCredential` using the VM's managed identity. The configured chat model is `openrouter/free`, and the embedding model is `nvidia/nemotron-3-embed-1b:free`. Both use OpenRouter.

Compose sets `BACKEND_URL=http://backend:5000` for the frontend. `IMAGE_TAG` selects the application image version and defaults to `latest` for manual commands.

### Automated deployment

Add these secrets under the GitHub repository's **Settings → Secrets and variables → Actions**:

| Secret name | Required value |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token with read/write permissions |
| `AZURE_CREDENTIALS` | Service principal JSON containing `clientId`, `clientSecret`, `subscriptionId`, and `tenantId` |
| `RESOURCE_GROUP_NAME` | Resource group containing the VM |
| `VM_NAME` | Deployment VM name |

Give the service principal permission to invoke commands on the VM. Use public Docker Hub repositories named `chatbot-backend` and `chatbot-frontend` so the VM can pull the images without a registry token.

The VM also needs a read-only SSH deploy key for the GitHub repository. `update_app.sh` expects the private key at `/home/azureuser/.ssh/github_deploy`, a verified GitHub host entry in `known_hosts`, and the repository at `/home/azureuser/chatbot-project-CloudComputing`. Set the private key's permissions to `400`. If the VM username or directory differs, update the paths in both `update_app.sh` and `.github/workflows/deploy.yml`.

Once configured, a push to `main` starts the workflow. It builds and publishes both images, then invokes the update script through Azure CLI. The script retrieves the source and runs images tagged with the same commit SHA.

## 6. Known Issues

- User authentication and per-user chat isolation are not implemented. Stored conversations are shared across users of the application.
- Key Vault secrets are read only at startup. After updating a secret, run `docker compose restart backend`. Expired Blob Storage SAS tokens must be renewed and updated in the vault.
- The supplied deployment assumes an Azure VM with a managed identity. Running the application elsewhere requires separate Azure authentication and service connectivity.
- Python package versions are not pinned, so future dependency updates may require compatibility testing.
