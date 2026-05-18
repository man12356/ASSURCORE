#!/bin/bash
# =============================================================================
# rebuild_vps.sh — Remote rebuild and restore script for AssurCore
# =============================================================================

# Ensure execution halts on error if needed, but allow compose down warnings
set -e

echo "=== [1/6] Preparing Addons ==="
mkdir -p addons
cp -rf assurcore addons/

echo "=== [2/6] Stopping existing containers ==="
docker-compose down || true

echo "=== [3/6] Starting containers in background ==="
docker-compose up -d --build

echo "=== Installing python dependencies (openpyxl) ==="
docker-compose exec -u 0 -T web pip install openpyxl

echo "=== [4/6] Waiting for database container to be healthy ==="
sleep 15

echo "=== [5/6] Recreating PostgreSQL database assurcore_db ==="
# Stop Odoo container temporarily to close all active connections
docker-compose stop web || true
# Drop and recreate assurcore_db cleanly
docker-compose exec -T db dropdb -U odoo --if-exists assurcore_db || true
docker-compose exec -T db createdb -U odoo assurcore_db

echo "=== [6/6] Restoring PostgreSQL database dump ==="
docker-compose exec -T db pg_restore -U odoo -d assurcore_db /backups/assurcore_db.dump || true

echo "=== Restarting Odoo web service to clear cache ==="
docker-compose start web

echo "=== Rebuild sequence completed successfully! ==="
