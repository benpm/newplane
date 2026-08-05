#!/usr/bin/env bash
# Live log feed for the dev-site stack (https://dev.mousetrip.online).
#
# Prints a status header showing which containers are up, then streams logs
# until interrupted with Ctrl-C. Delegates to dev-site.sh so the compose
# project/env wiring lives in exactly one place.
#
#   ./scripts/dev-site-logs.sh                 all app services (default)
#   ./scripts/dev-site-logs.sh api             one service
#   ./scripts/dev-site-logs.sh api worker      several services
#   ./scripts/dev-site-logs.sh --all           include datastores (db/redis/mq/minio)
#   ./scripts/dev-site-logs.sh --tail 200 api  more scrollback (default 50)
#   ./scripts/dev-site-logs.sh --errors        only lines that look like problems
#   ./scripts/dev-site-logs.sh --list          show service names and exit
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_SITE="$SCRIPT_DIR/dev-site.sh"

# Application services carry the interesting output. Datastores are excluded by
# default because their chatter drowns out app logs; --all brings them back.
APP_SERVICES=(api worker beat-worker web admin space live proxy)
DATASTORES=(plane-db plane-redis plane-mq plane-minio)

TAIL=50
ERRORS_ONLY=0
INCLUDE_ALL=0
SERVICES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)    INCLUDE_ALL=1; shift ;;
    --errors) ERRORS_ONLY=1; shift ;;
    --tail)   TAIL="${2:?--tail needs a number}"; shift 2 ;;
    --list)
      printf 'app services: %s\n' "${APP_SERVICES[*]}"
      printf 'datastores:   %s\n' "${DATASTORES[*]}"
      exit 0 ;;
    -h|--help)
      # Print the header comment block, stopping at the first non-comment line
      # so this stays correct if the header grows.
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "${BASH_SOURCE[0]}"
      exit 0 ;;
    -*)       echo "unknown option: $1 (try --help)" >&2; exit 1 ;;
    *)        SERVICES+=("$1"); shift ;;
  esac
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  SERVICES=("${APP_SERVICES[@]}")
  [[ $INCLUDE_ALL -eq 1 ]] && SERVICES+=("${DATASTORES[@]}")
fi

# Status header — makes it obvious when something is down rather than merely quiet.
echo "── dev site: https://dev.mousetrip.online (localhost:8091) ──"
"$DEV_SITE" ps --format '  {{.Service}}\t{{.State}}\t{{.Status}}' 2>/dev/null \
  || echo "  (could not read stack status)"
printf '── following: %s (last %s lines, Ctrl-C to stop)' "${SERVICES[*]}" "$TAIL"
[[ $ERRORS_ONLY -eq 1 ]] && printf ' [errors only]'
printf ' ──\n\n'

# --no-log-prefix is NOT used: the service prefix is what makes a combined
# stream readable. Compose exits non-zero on Ctrl-C, so tolerate that.
if [[ $ERRORS_ONLY -eq 1 ]]; then
  # --line-buffered keeps the feed live rather than block-buffered through grep.
  "$DEV_SITE" logs --follow --tail "$TAIL" "${SERVICES[@]}" 2>&1 \
    | grep --line-buffered -iE 'error|exception|traceback|critical|fatal|failed|warn' \
    || true
else
  "$DEV_SITE" logs --follow --tail "$TAIL" "${SERVICES[@]}" || true
fi
