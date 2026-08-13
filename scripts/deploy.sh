#!/usr/bin/env bash
# Deploys the current main branch to production on this machine.
# Run from a clone of the repo on the production host itself
# (docker-compose.prod.yml, .env, and ssl/ must already be in place).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

echo "==> Checking for local changes..."
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: uncommitted local changes on this machine. Aborting." >&2
  git status --short
  exit 1
fi

echo "==> Pulling latest main..."
git fetch origin main
git merge --ff-only origin/main

echo "==> Building and starting services..."
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Waiting for backend to be ready..."
ready=false
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/ready > /dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [ "$ready" != true ]; then
  echo "ERROR: backend did not become ready in time." >&2
  docker compose -f docker-compose.prod.yml logs backend --tail 50
  exit 1
fi

echo "==> Verifying the site locally..."
site_up=false
for _ in $(seq 1 15); do
  if curl -skf -o /dev/null --resolve "${PUBLIC_DOMAIN}:443:127.0.0.1" "https://${PUBLIC_DOMAIN}/"; then
    site_up=true
    break
  fi
  sleep 2
done
if [ "$site_up" != true ]; then
  echo "ERROR: local site check failed after deploy." >&2
  docker compose -f docker-compose.prod.yml logs caddy --tail 50
  exit 1
fi

echo "==> Cleaning up dangling images..."
docker image prune -f > /dev/null

echo "Deploy succeeded: https://${PUBLIC_DOMAIN}/ is responding."
