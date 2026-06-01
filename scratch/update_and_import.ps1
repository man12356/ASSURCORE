# ============================================================
#  update_and_import.ps1
#  Mise à jour module Odoo + Import données réelles
#  Exécuter depuis : d:\Robot\ASSURPROD
# ============================================================

$ErrorActionPreference = "Continue"
$Cwd = "d:\Robot\ASSURPROD"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ÉTAPE 1 — Arrêt du conteneur web Odoo" -ForegroundColor Cyan
Write-Host "============================================================"
docker compose -p assurcore stop web
if ($LASTEXITCODE -ne 0) { Write-Host "ERREUR arrêt web" -ForegroundColor Red; exit 1 }
Write-Host "✓ Conteneur web arrêté" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ÉTAPE 2 — Mise à jour du module assurcore" -ForegroundColor Cyan
Write-Host "  (applique les nouveaux champs + menus réorganisés)" -ForegroundColor Yellow
Write-Host "============================================================"
docker compose -p assurcore run --rm web odoo -d assurcore_db -u assurcore --stop-after-init
if ($LASTEXITCODE -ne 0) { Write-Host "AVERTISSEMENT: vérifier les logs ci-dessus" -ForegroundColor Yellow }
Write-Host "✓ Module mis à jour" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ÉTAPE 3 — Redémarrage du conteneur web" -ForegroundColor Cyan
Write-Host "============================================================"
docker compose -p assurcore start web
Start-Sleep -Seconds 10
Write-Host "✓ Odoo redémarré" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ÉTAPE 4 — Test DRY-RUN (aucune écriture)" -ForegroundColor Cyan
Write-Host "============================================================"
python "$Cwd\migration_scripts\import_assurcore_v2.py" --dry-run --file "$Cwd\DATA_REEL_22-05-2026\DATA_REEL"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ÉTAPE 5 — Import réel des données" -ForegroundColor Cyan
Write-Host "============================================================"
$confirm = Read-Host "Lancer l'importation réelle ? (o/n)"
if ($confirm -eq 'o' -or $confirm -eq 'O') {
    python "$Cwd\migration_scripts\import_assurcore_v2.py" --file "$Cwd\DATA_REEL_22-05-2026\DATA_REEL"
    Write-Host ""
    Write-Host "✅ Import terminé ! Consultez le log : $Cwd\migration_scripts\import_assurcore_v2.log" -ForegroundColor Green
} else {
    Write-Host "Import annulé." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ TERMINÉ — Vérifiez Odoo sur http://localhost:8071" -ForegroundColor Green
Write-Host "============================================================"
