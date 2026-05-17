#!/bin/bash
# =============================================================================
# rebuild_vps.sh — Remote rebuild and restore script for AssurCore
# =============================================================================

# Ensure execution halts on error if needed, but allow compose down warnings
set -e

echo "=== [1/5] Preparing Addons ==="
mkdir -p addons
cp -rf assurcore addons/

echo "=== [2/5] Stopping existing containers ==="
docker-compose down || true

echo "=== [3/5] Starting containers in background ==="
docker-compose up -d --build

echo "=== [4/5] Waiting for database container to be healthy ==="
sleep 15

echo "=== [5/5] Restoring PostgreSQL database dump ==="
docker-compose exec -T db pg_restore -U odoo -d postgres_system --clean --create /var/lib/postgresql/data/assurcore_db.dump

echo "=== Restarting Odoo web service to clear cache ==="
docker-compose restart web

echo "=== Rebuild sequence completed! ==="
