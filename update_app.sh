#!/usr/bin/env bash
set -Eeuo pipefail

cd /home/azureuser/chatbot-project-CloudComputing
export GIT_SSH_COMMAND='ssh -i /home/azureuser/.ssh/github_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes'

git fetch origin main
revision="${1:-$(git rev-parse origin/main)}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA'; exit 1; }
git merge-base --is-ancestor "$revision" origin/main
git checkout --detach "$revision"
chmod +x update_app.sh

export IMAGE_TAG="$revision"
docker compose config --quiet
docker compose pull backend chatbot
docker compose up -d --no-build --wait --wait-timeout 180
curl --fail --silent --show-error http://127.0.0.1:5000/health/
curl --fail --silent --show-error http://127.0.0.1:8501/_stcore/health
