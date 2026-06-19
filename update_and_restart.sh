#!/bin/sh
set -e
cd /volume1/docker/firesport-app || exit 1
if command -v git >/dev/null 2>&1; then
  git fetch origin
  git checkout proudction || true
  git reset --hard origin/proudction || true
else
  echo "git not found on host — skipping git update"
fi
if command -v docker-compose >/dev/null 2>&1; then
  dc=docker-compose
else
  dc="docker compose"
fi
$dc -f docker-compose.yml pull || true
$dc -f docker-compose.yml up -d --build
