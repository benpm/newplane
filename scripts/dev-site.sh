#!/usr/bin/env bash
# Drive the isolated dev-site stack (compose project "planedev").
#
# The dev site is a full second Plane deployment built from the current working
# tree. It shares nothing with production: separate images, volumes, network,
# database, object store and crypto keys.
#
#   production -> https://plane.mousetrip.online   (localhost:8090)
#   dev site   -> https://dev.mousetrip.online     (localhost:8091)
#
# Use this wrapper rather than raw `docker compose`: a bare compose command in
# this directory resolves to the PRODUCTION stack.
#
#   ./scripts/dev-site.sh up -d          start / restart
#   ./scripts/dev-site.sh build          rebuild images from the working tree
#   ./scripts/dev-site.sh logs -f api    follow a service
#   ./scripts/dev-site.sh ps             status
#   ./scripts/dev-site.sh down           stop (volumes and data are kept)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_ENV_DIR="/home/beb/live/plane-dev-env"

if [[ ! -f "$DEV_ENV_DIR/root.env" || ! -f "$DEV_ENV_DIR/api.env" ]]; then
  echo "error: dev env files missing under $DEV_ENV_DIR" >&2
  exit 1
fi

exec docker compose \
  --project-name planedev \
  --project-directory "$REPO_ROOT" \
  --env-file "$DEV_ENV_DIR/root.env" \
  -f "$REPO_ROOT/docker-compose.yml" \
  -f "$REPO_ROOT/docker-compose.devsite.yml" \
  "$@"
