#!/usr/bin/env bash
# Deploy HUG on the shared server. Run as the `deploy` user (docker group) from anywhere:
#   /opt/hug-ai/deploy/deploy.sh
# Needs deploy/.env (see deploy/.env.example).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; . deploy/.env; set +a
: "${PROXY_NETWORK:?}" "${PROXY_CADDYFILE:?}" "${PROXY_CONTAINER:?}" "${APP_HOST:?}"

COMPOSE=(docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env)

if [ "${SKIP_PULL:-0}" != "1" ]; then
  echo "==> pull"
  git pull --ff-only
  # Bash keeps running the old copy of this file after the pull replaces it; restart with the new one.
  SKIP_PULL=1 exec "$0" "$@"
fi

echo "==> build + up"
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "==> wait for health"
for i in $(seq 1 40); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$("${COMPOSE[@]}" ps -q api)" 2>/dev/null || echo starting)
  [ "$status" = healthy ] && break
  sleep 3
done
echo "    api: $status"
[ "$status" = healthy ] || { "${COMPOSE[@]}" logs --tail 60 api; exit 1; }

echo "==> ensure reverse-proxy route for $APP_HOST"
# The route is committed to the portfelim-backend Caddyfile; this is a fallback if it goes missing.
if ! grep -qE "^${APP_HOST//./\\.} \{" "$PROXY_CADDYFILE"; then
  TEE=(tee -a); [ -w "$PROXY_CADDYFILE" ] || TEE=(sudo tee -a)
  printf '\n# HUG voice assistant (/opt/hug-ai, managed by hug-ai/deploy/deploy.sh)\n%s {\n\tencode zstd gzip\n\treverse_proxy hug-api:8000\n}\n' "$APP_HOST" \
    | "${TEE[@]}" "$PROXY_CADDYFILE" >/dev/null
  docker exec "$PROXY_CONTAINER" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  docker exec "$PROXY_CONTAINER" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
fi

echo "==> prune dangling images"
docker image prune -f >/dev/null

echo "==> smoke test https://$APP_HOST"
curl -fsS "https://$APP_HOST/health" && echo
curl -fsS "https://$APP_HOST/api/v1/assistant/capabilities" && echo
"${COMPOSE[@]}" ps
