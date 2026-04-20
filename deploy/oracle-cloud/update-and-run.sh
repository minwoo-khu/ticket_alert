#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ticket_alert}"
REPO_URL="${REPO_URL:-https://github.com/minwoo-khu/ticket_alert.git}"
BRANCH="${BRANCH:-main}"

mkdir -p "$(dirname "$APP_DIR")"

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Edit $APP_DIR/.env and $APP_DIR/worker.json, then rerun this script."
  exit 0
fi

mkdir -p runtime runtime/profiles runtime/screenshots

docker compose up -d --build
docker compose ps

cat <<EOF

Worker is starting.

Useful commands:
  cd $APP_DIR
  docker compose logs -f
  docker compose ps
  docker compose restart

EOF
