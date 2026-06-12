# ==============================================================================
#  RUN_REIMPORT_COMPLET.ps1 — Re-import integral des donnees metier (SQL direct)
#  Config societe + utilisateurs PRESERVES.
#  Etapes : sauvegarde -> generation SQL -> reset+import -> recalculs ->
#           lot 4 (FIFO + anomalies) -> tests EVO02 -> redemarrage
# ==============================================================================
$ErrorActionPreference = 'Continue'
Set-Location 'D:\Robot\ASSURPROD'
function Step($m){ Write-Host "`n========== $m" -ForegroundColor Cyan }

Step "0/7 Sauvegarde de la base actuelle"
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
docker compose exec db pg_dump -U odoo -d assurcore_db -F c -f /backups/avant_reimport_$stamp.dump
Write-Host "Dump : data_db\avant_reimport_$stamp.dump"

Step "1/7 Copie des sources dans le volume addons"
if (-not (Test-Path .\addons\DATA_REEL)) {
    Copy-Item -Recurse .\DATA_REEL_22-05-2026\DATA_REEL .\addons\DATA_REEL -Force
}
Copy-Item .\migration_scripts\evo02_full_etl.py  .\addons\ -Force
Copy-Item .\migration_scripts\evo02_recompute.py .\addons\ -Force
Copy-Item .\migration_scripts\evo02_lot4_migration.py .\addons\ -Force

Step "2/7 Generation du SQL (dans le conteneur web — SQL direct, REX projet)"
docker compose run --rm -T web python3 /mnt/extra-addons/evo02_full_etl.py
if ($LASTEXITCODE -ne 0) { Write-Host "ECHEC generation" -ForegroundColor Red; exit 1 }
Copy-Item .\addons\evo02_full_import.sql .\data_db\ -Force

Step "3/7 RESET + IMPORT (psql, une transaction)"
docker compose stop web | Out-Null
docker compose exec db psql -U odoo -d assurcore_db -v ON_ERROR_STOP=1 -f /backups/evo02_full_import.sql
if ($LASTEXITCODE -ne 0) { Write-Host "ECHEC import SQL — base inchangee (ROLLBACK)" -ForegroundColor Red; exit 1 }

Step "4/7 Recalcul des statuts (ident_mode, settlement_state)"
docker compose run --rm -T web sh -c "odoo shell -c /etc/odoo/odoo.conf -d assurcore_db --no-http < /mnt/extra-addons/evo02_recompute.py" 2>&1 | Tee-Object -FilePath .\evo02_recompute_result.log

Step "5/7 Lot 4 : ventilation FIFO + anomalies + recette"
docker compose run --rm -T web sh -c "odoo shell -c /etc/odoo/odoo.conf -d assurcore_db --no-http < /mnt/extra-addons/evo02_lot4_migration.py" 2>&1 | Tee-Object -FilePath .\evo02_lot4_result.log

Step "6/7 Tests EVO02"
docker compose run --rm -T web odoo -c /etc/odoo/odoo.conf -d assurcore_db -u assurcore --test-tags evo02 --stop-after-init --workers 0 2>&1 | Tee-Object -FilePath .\evo02_test_result.log | Select-String -Pattern "tests.result|FAIL|ERROR " | Select-Object -First 5

Step "7/7 Redemarrage"
docker compose up -d web | Out-Null
Write-Host "`nTermine. Verifier : evo02_lot4_result.log (recette) + http://localhost:8071" -ForegroundColor Green
