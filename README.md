# Cloud Chatbot — Project Stage 7

## 1. Project Summary

This application supports regular AI conversations and questions about uploaded PDF documents. Users can create, save, load, and delete chats through a Streamlit interface connected to a FastAPI backend.

- **OpenRouter** provides chat responses using `openrouter/free` and embeddings using `nvidia/nemotron-3-embed-1b:free`.
- **ChromaDB** stores document embeddings in a persistent Docker volume on the Azure VM.
- **Azure Database for PostgreSQL** stores chat metadata in `appdb`.
- **Azure Blob Storage** stores chat messages and uploaded PDFs.
- **Azure Key Vault** stores the application's secrets.
- **Terraform** manages the project's database, storage, Key Vault, VM identity, and vault permissions. **GitHub Actions** builds Docker images and deploys them to the existing Azure VM.

## 2. Requirements

- An Azure account with an existing Linux VM, PostgreSQL Flexible Server, Blob Storage account/container, and permission to manage Key Vault and role assignments.
- An OpenRouter account and API key. An OpenAI API key is not used.
- GitHub and Docker Hub accounts for automated deployment.
- Git, Docker Engine, and Docker Compose on the VM.
- Azure CLI and Terraform 1.5 or newer, below 2.0, for infrastructure setup. Provider versions are declared in `terraform/providers.tf` and the lock file.
- Python 3.12 for installing or running Python tools outside Docker; the Dockerfiles include Python themselves.
- DBeaver or another PostgreSQL client for database setup.

Python packages are listed in `requirements.txt`, including Streamlit, FastAPI, Uvicorn, LangChain, ChromaDB, the OpenAI-compatible client used with OpenRouter, PostgreSQL and Azure SDKs, and PDF processing libraries.

## 3. Installation

On the Azure VM, configure a read-only GitHub deploy key for this private repository. The deployment script expects the private key at `/home/azureuser/.ssh/github_deploy`, with its public key added to the repository's Deploy keys and GitHub's host keys verified in `known_hosts`.

```bash
cd /home/azureuser
GIT_SSH_COMMAND='ssh -i /home/azureuser/.ssh/github_deploy -o IdentitiesOnly=yes' \
  git clone git@github.com:shahadalyahya04/chatbot-project-CloudComputing.git
cd chatbot-project-CloudComputing
cp .env.example .env
```

Fill in `.env` and configure the Key Vault secrets described in section 5. Docker installs the Python dependencies when building images. For a separate Python development environment, install them with:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For this project's infrastructure, authenticate with Azure CLI, copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`, and fill in the subscription and resource names. Then run:

```bash
az login
cd terraform
terraform init
terraform plan
terraform apply
cd ..
```

The Terraform files target this project's existing resources and import IDs. Review them before applying to a different Azure environment; they do not create a new VM or network from scratch.

Create the `appdb` database if it does not exist, allow the VM and your client IP through PostgreSQL's firewall, and run `setup_appdb.sql` as the database administrator while connected to `appdb`. This creates `appuser`, creates `advanced_chats`, and grants the required permissions.

## 4. Run the Project

On the configured Azure VM, use the published images:

```bash
cd /home/azureuser/chatbot-project-CloudComputing
docker compose pull backend chatbot
docker compose up -d --no-build --wait
docker compose ps
```

To build the images from the source on the VM instead:

```bash
docker compose up -d --build --wait
```

Open `http://<VM_PUBLIC_IP>:8501` in your browser. The current deployment is at [http://20.83.152.195:8501](http://20.83.152.195:8501). Allow inbound TCP port 8501 in the VM's network security group.

Check the backend from inside the VM:

```bash
curl --fail http://127.0.0.1:5000/health/
```

Compose starts Streamlit, FastAPI, and ChromaDB together. The backend's port 5000 is bound to the VM's loopback interface. Keep the Compose project name `stage3_azure` and volume `stage3_azure_chroma_azure_data` to retain existing vector data.

For automated updates, push application changes to `main`. `.github/workflows/deploy.yml` builds and pushes the backend and frontend images to Docker Hub, then uses Azure CLI to run `update_app.sh` on the VM. The script pulls the repository and deploys images tagged with that commit's SHA.

## 5. API Keys & Environment Variables

The VM's `.env` contains only these two settings:

```dotenv
KEY_VAULT_NAME=shahad-chatbot-kv
DOCKERHUB_NAMESPACE=shahad555
```

Store the following values as secrets in Azure Key Vault:

| Key Vault secret | Value |
| --- | --- |
| `PROJ-DB-NAME` | `appdb` |
| `PROJ-DB-USER` | `appuser` |
| `PROJ-DB-PASSWORD` | The application database user's password |
| `PROJ-DB-HOST` | PostgreSQL server hostname |
| `PROJ-DB-PORT` | `5432` |
| `PROJ-OPENROUTER-API-KEY` | Your OpenRouter API key |
| `PROJ-AZURE-STORAGE-SAS-URL` | Blob service SAS URL with the required storage permissions |
| `PROJ-AZURE-STORAGE-CONTAINER` | `chatbot-files` |
| `PROJ-CHROMADB-HOST` | `chromadb` for the supplied Compose network |
| `PROJ-CHROMADB-PORT` | `8000` |

The OpenRouter secret replaces the assignment's OpenAI secret name. The backend uses `DefaultAzureCredential` and the VM's managed identity, which needs the **Key Vault Secrets User** role on the vault. Terraform configures this access. Values are populated outside Terraform and are not committed to Git.

Compose sets the frontend's `BACKEND_URL` to `http://backend:5000`. The deployment script sets `IMAGE_TAG` to the commit SHA; manual Compose commands default to `latest`.

Add these GitHub repository Actions secrets for automated deployment:

| GitHub secret | Purpose |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub token with read/write permissions |
| `AZURE_CREDENTIALS` | Service principal JSON containing `clientId`, `clientSecret`, `subscriptionId`, and `tenantId` |
| `RESOURCE_GROUP_NAME` | `chatbot-RG` |
| `VM_NAME` | `chatbot-vm` |

The deployment service principal needs permission to invoke commands on the VM. The Docker Hub repositories `shahad555/chatbot-backend` and `shahad555/chatbot-frontend` are public so the VM can pull images without storing a Docker Hub token.

## 6. Known Issues

- The application does not implement user login or separate each user's stored chats. Authentication and user isolation are future improvements.
- Secrets are loaded when the backend starts. After changing a Key Vault value, restart the backend with `docker compose restart backend`. Renew the Blob Storage SAS before it expires and update its Key Vault secret.
- Running Compose on a personal computer requires separate Azure authentication and access to the cloud services. The supplied setup is configured for the Azure VM's managed identity.
- Python dependency versions are not pinned in `requirements.txt`; future package updates may require compatibility checks.
