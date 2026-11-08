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

**Just push to `main`.** That's it:

1. GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests, a JS syntax check
   and a Docker build for the commit.
2. On the server, `hug-autodeploy.timer` runs `deploy/autodeploy.sh` every minute. When
   `origin/main` has a new commit **and its CI finished green**, it runs `deploy/deploy.sh`.
   A red build is skipped (and not retried) — production keeps the last good version.
3. `deploy.sh` pulls, rebuilds, waits for the health check, ensures the Caddy route,
   and smoke-tests the public URL.

Typical push-to-live time: CI (~2–3 min) + up to 1 min + build (~1 min).

Why pull-based: the repo's owner holds the GitHub secrets, and this way no SSH key
lives in GitHub and nothing connects into the server.

```bash
ssh portfelim-hz 'journalctl -u hug-autodeploy -n 30 --no-pager'   # what auto-deploy did
ssh portfelim-hz 'systemctl list-timers hug-autodeploy.timer'        # next check
ssh portfelim-hz 'sudo -u deploy /opt/hug-ai/deploy/deploy.sh'       # manual deploy (skips CI)
ssh portfelim-hz 'systemctl disable --now hug-autodeploy.timer'      # pause auto-deploy
```

The units live in `deploy/systemd/`; install or update them as root:
```bash
cp /opt/hug-ai/deploy/systemd/hug-autodeploy.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now hug-autodeploy.timer
```

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

## Care features (SOS, medicines, check-in, family circle)

- Web Push needs a VAPID key pair in `deploy/.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
  `VAPID_SUBJECT`). Generate once with `py_vapid` (see `backend/app/services/push_service.py`);
  rotating the keys invalidates every existing subscription.
- `PUBLIC_BASE_URL` builds the family invite links (`/f/<token>`).
- A scheduler inside the single API worker runs every 30 s: medicine due → push to the elder;
  not taken in 30 min → "missed" + push to family; daily check-in prompt at the elder's time,
  family alert if unanswered for 2 h; one-off reminders are pushed when due.
- All care data lives in new tables in the same SQLite volume.
