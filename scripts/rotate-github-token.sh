#!/usr/bin/env bash
# Rotate GITHUB_PERSONAL_ACCESS_TOKEN for the GitHub issue/wiki sync.
#
# The token is read from a hidden prompt, never from argv or a file you have to
# clean up, so it stays out of shell history and the process table.
#
# It is validated against the GitHub API *before* anything is written: an
# invalid or under-scoped token is rejected rather than silently deployed.
#
#   Usage: bash scripts/rotate-github-token.sh [--no-restart]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILES=("$REPO_ROOT/.env" "$REPO_ROOT/apps/api/.env")
KEY="GITHUB_PERSONAL_ACCESS_TOKEN"
RESTART=true
[ "${1:-}" = "--no-restart" ] && RESTART=false

# The sync pushes wiki commits and PATCHes issue state, so read-only is not enough.
NEEDED_SCOPE="repo"

printf 'New GitHub token (input hidden): ' >&2
read -rs TOKEN
printf '\n' >&2
[ -n "$TOKEN" ] || { echo "ERROR: empty token, nothing changed." >&2; exit 1; }

echo "==> Validating against the GitHub API..." >&2
hdrs=$(curl -sS -D - -o /dev/null \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user)

code=$(printf '%s' "$hdrs" | awk 'NR==1{print $2}')
if [ "$code" != "200" ]; then
  echo "ERROR: GitHub rejected the token (HTTP $code). Nothing changed." >&2
  exit 1
fi

login=$(curl -sS -H "Authorization: Bearer $TOKEN" https://api.github.com/user \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("login","?"))')
scopes=$(printf '%s' "$hdrs" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{print $2}')
echo "    authenticated as: $login" >&2
echo "    scopes: ${scopes:-<none reported>}" >&2

# Fine-grained tokens report no scopes; only gate classic tokens on the header.
if [ -n "$scopes" ] && ! printf '%s' "$scopes" | grep -qw "$NEEDED_SCOPE"; then
  echo "ERROR: token lacks the '$NEEDED_SCOPE' scope (wiki push + issue state need write)." >&2
  echo "       Nothing changed." >&2
  exit 1
fi

echo "==> Checking write access to each configured repo..." >&2
repos=$(docker exec plane-db psql -U plane -d plane -tAc \
  "SELECT repository_owner||'/'||repository_name FROM project_github_syncs;" 2>/dev/null || true)
if [ -z "$repos" ]; then
  echo "    (no syncs configured — skipping)" >&2
else
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    push=$(curl -sS -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/$r" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("permissions",{}).get("push", d.get("message","?")))')
    echo "    $r -> push=$push" >&2
    if [ "$push" != "True" ]; then
      echo "ERROR: no write access to $r. Nothing changed." >&2
      exit 1
    fi
  done <<< "$repos"
fi

echo "==> Writing token to env files..." >&2
for f in "${ENV_FILES[@]}"; do
  [ -f "$f" ] || { echo "    skip (missing): $f" >&2; continue; }
  cp -p "$f" "$f.bak-$(date +%Y%m%d-%H%M%S)"
  KEY="$KEY" TOKEN="$TOKEN" python3 - "$f" <<'PY'
import os, sys, pathlib
key, token, path = os.environ["KEY"], os.environ["TOKEN"], pathlib.Path(sys.argv[1])
lines = path.read_text().splitlines(keepends=True)
out, seen = [], False
for ln in lines:
    if ln.split("=", 1)[0].strip() == key:
        out.append(f"{key}={token}\n"); seen = True
    else:
        out.append(ln)
if not seen:
    if out and not out[-1].endswith("\n"):
        out.append("\n")
    out.append(f"{key}={token}\n")
path.write_text("".join(out))
PY
  echo "    updated: $f (backup alongside)" >&2
done

if [ "$RESTART" = true ]; then
  echo "==> Restarting api, worker, beat-worker..." >&2
  (cd "$REPO_ROOT" && docker compose up -d --force-recreate api worker beat-worker >/dev/null 2>&1)
  echo "    done" >&2
fi

echo >&2
echo "Token rotated. The sync retries every 5 minutes; watch it with:" >&2
echo "  docker logs bgworker --since 6m 2>&1 | grep -i github" >&2
