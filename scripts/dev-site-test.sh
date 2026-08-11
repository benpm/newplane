#!/usr/bin/env bash
# Run the backend test suite against the dev-site datastores.
#
# The runtime api image ships no test dependencies, and containers on this host
# have no outbound network, so the image is built once with --network host from
# requirements/test.txt layered on top of planedev-api.
#
# The repo is mounted at /repo rather than /code because some tests locate the
# repo root by parent depth from apps/api, so the real layout must be preserved.
#
#   ./scripts/dev-site-test.sh -m unit                 unit tests
#   ./scripts/dev-site-test.sh plane/tests/unit/views  a subset
#   ./scripts/dev-site-test.sh -m unit --cov=plane     with coverage
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE=plane-api-test:latest

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "building $IMAGE (test deps on top of planedev-api)..." >&2
  tmp=$(mktemp -d)
  # git is a test-only dependency: the wiki-sync tests seed a local bare repo as
  # a stand-in for a GitHub wiki. The task itself talks to the GitHub API over
  # requests, so the runtime image deliberately has no git.
  cat > "$tmp/Dockerfile" <<'EOF'
FROM planedev-api:latest
USER root
RUN apk add --no-cache git
COPY requirements /tmp/requirements
RUN pip install --no-cache-dir -r /tmp/requirements/test.txt
EOF
  docker build --network host -f "$tmp/Dockerfile" -t "$IMAGE" "$REPO_ROOT/apps/api" >&2
  rm -rf "$tmp"
fi

exec docker run --rm --network planedev_default -w /repo/apps/api \
  -e DJANGO_SETTINGS_MODULE=plane.settings.test \
  -e DATABASE_URL=postgresql://plane:plane@plane-db:5432/plane \
  -e REDIS_URL=redis://plane-redis:6379/ \
  -e SECRET_KEY=test-secret-key-for-pytest \
  -e AWS_ACCESS_KEY_ID=access-key -e AWS_SECRET_ACCESS_KEY=secret-key \
  -e AWS_S3_ENDPOINT_URL=http://plane-minio:9000 -e AWS_S3_BUCKET_NAME=uploads -e USE_MINIO=1 \
  -v "$REPO_ROOT":/repo:rw \
  "$IMAGE" \
  python -m pytest --no-header --nomigrations -p no:cacheprovider "$@"
