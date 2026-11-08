# Deploying HUG

| | |
|---|---|
| **URL** | https://hug.46-224-126-66.sslip.io |
| **Server** | Hetzner box `46.224.126.66` (hostname `jabish-1`), shared with Portfelim, EcoTrail, ODLAR, Jabish and the static sites |
| **ssh** | `ssh portfelim-hz` (root, `~/.ssh/id_ed25519_2`); deploys run as the `deploy` user |
| **Code** | `/opt/hug-ai` — a clone of `github.com/nnrmina/hug-ai` (`main`) |
| **Runtime** | one Docker container `hug-ai-api-1` (compose project `hug-ai`), alias `hug-api` on the `portfelim_default` network, no host ports |
| **HTTPS** | the shared Caddy (`portfelim-caddy-1`) proxies `hug.46-224-126-66.sslip.io` → `hug-api:8000` and renews the Let's Encrypt certificate itself |
| **Data** | Docker volume `hug-ai_hug-data` → `/data` in the container: `hug.db` (SQLite) and `tts_cache/` |
| **Secrets** | `/opt/hug-ai/deploy/.env` (mode 600, never committed) — see `deploy/.env.example` |

## Deploy a new version

```bash
git push origin main                       # from your machine
ssh portfelim-hz 'sudo -u deploy /opt/hug-ai/deploy/deploy.sh'
```

`deploy.sh` pulls `main`, rebuilds the image, waits for the container health check,
makes sure the Caddy route exists, and smoke-tests the public URL. There is **no
auto-deploy**: pushing alone changes nothing on the server.

## Things that are easy to get wrong

- **One worker only.** Conversation memory and pending confirmations live in process
  memory (`--workers 1` in the Dockerfile). More workers would make follow-ups and
  "Bəli" confirmations land on a process that never saw the question. Scale with Redis first.
- **The Caddy route lives in another repo.** The `hug.46-224-126-66.sslip.io` block is
  committed in `portfelim-backend/deploy/Caddyfile`. Portfelim's own deploy does a
  `git reset --hard`, so a route added only on the server would vanish; `deploy.sh`
  re-adds it as a fallback.
- **HTTPS is not optional.** Phones only allow the microphone on secure origins.
- **Memory limit 384 MB.** The box has ~4 GB shared by ~14 containers.
- **Gemini free tier:** 15 requests/min, 500/day on `gemini-3.5-flash-lite`. Over the
  limit the app falls back to rule-based understanding (badge shows "Sadə rejim").

## Operate

```bash
ssh portfelim-hz
cd /opt/hug-ai
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env ps
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env logs -f --tail 100 api
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env restart api
```

Backup the database (SQLite online backup, safe while running):

```bash
docker exec hug-ai-api-1 python -c "import sqlite3; s=sqlite3.connect('/data/hug.db'); d=sqlite3.connect('/data/hug-backup.db'); s.backup(d)"
docker cp hug-ai-api-1:/data/hug-backup.db ./hug-$(date +%F).db
```

Change a secret: edit `/opt/hug-ai/deploy/.env`, then `deploy.sh` (or `up -d` to restart).
