#!/usr/bin/env bash
# Pull-based auto-deploy, run every minute by hug-autodeploy.timer as the `deploy` user.
#
# When origin/main has a new commit, deploy it — but only once GitHub Actions (CI) has
# finished green for that exact commit. Red builds are skipped and never retried; a new
# push is needed. No secrets live in GitHub and nothing connects into the server.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$REPO_DIR/deploy/.state"
REPO_SLUG="${HUG_GITHUB_REPO:-nnrmina/hug-ai}"
mkdir -p "$STATE_DIR"

# One run at a time (a deploy can outlast the 1-minute timer)
exec 9>"$STATE_DIR/lock"
flock -n 9 || exit 0

cd "$REPO_DIR"
git fetch -q origin main
remote=$(git rev-parse origin/main)
local_sha=$(git rev-parse HEAD)
[ "$remote" = "$local_sha" ] && exit 0

# Already decided this commit is red? Stay quiet until something new is pushed.
[ "$(cat "$STATE_DIR/failed_sha" 2>/dev/null || true)" = "$remote" ] && exit 0

verdict=$(curl -fsS -m 15 -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO_SLUG/commits/$remote/check-runs?per_page=100" \
  | python3 -c '
import json, sys
runs = [r for r in json.load(sys.stdin).get("check_runs", []) if r.get("app", {}).get("slug") == "github-actions"]
if not runs:
    print("waiting")          # CI not started yet
elif any(r["status"] != "completed" for r in runs):
    print("waiting")          # CI still running
elif all(r["conclusion"] in ("success", "skipped", "neutral") for r in runs):
    print("green")
else:
    print("red")
' ) || { echo "could not reach GitHub API; will retry"; exit 0; }

short=${remote:0:7}
case "$verdict" in
  waiting) echo "new commit $short: waiting for CI"; exit 0 ;;
  red)     echo "new commit $short: CI failed, NOT deploying"; echo "$remote" > "$STATE_DIR/failed_sha"; exit 0 ;;
  green)   echo "new commit $short: CI green, deploying" ;;
esac

if "$REPO_DIR/deploy/deploy.sh"; then
  echo "deployed $short"
else
  echo "deploy of $short FAILED"
  exit 1
fi
