#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ticket_alert}"
SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"

echo "[1/5] Updating apt metadata"
sudo apt-get update

echo "[2/5] Installing base packages"
sudo apt-get install -y ca-certificates curl git

if ! sudo swapon --show | grep -q .; then
  total_mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  if [ "${total_mem_kb:-0}" -lt 2000000 ]; then
    echo "[2b/5] Enabling ${SWAP_SIZE_GB}G swap for low-memory shape"
    sudo fallocate -l "${SWAP_SIZE_GB}G" /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_SIZE_GB * 1024))
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '^/swapfile ' /etc/fstab; then
      echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    fi
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[3/5] Installing Docker engine"
  sudo apt-get install -y docker.io
else
  echo "[3/5] Docker already installed"
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[4/5] Installing Docker Compose plugin"
  if apt-cache show docker-compose-plugin >/dev/null 2>&1; then
    sudo apt-get install -y docker-compose-plugin
  elif apt-cache show docker-compose-v2 >/dev/null 2>&1; then
    sudo apt-get install -y docker-compose-v2
  else
    echo "Could not find a Docker Compose plugin package on this Ubuntu image."
    echo "Install Docker Compose manually, then rerun this script."
    exit 1
  fi
else
  echo "[4/5] Docker Compose already installed"
fi

echo "[5/5] Enabling Docker and preparing app directory"
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true
sudo mkdir -p "$APP_DIR"
sudo chown "$USER":"$USER" "$APP_DIR"

cat <<EOF

Bootstrap complete.

Next:
1. Reconnect your SSH session so the docker group applies.
2. Run:
   APP_DIR=$APP_DIR REPO_URL=https://github.com/minwoo-khu/ticket_alert.git bash ./deploy/oracle-cloud/update-and-run.sh

EOF
