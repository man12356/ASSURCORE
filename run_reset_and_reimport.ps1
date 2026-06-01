#Requires -Version 5.1
<#
.SYNOPSIS
    Reset complet des données métier + re-import depuis DATA_REEL.
    Conserve : configuration entreprise, utilisateurs, mailing, profils.
    Supprime et re-importe : clients, polices, quittances, règlements,
                             lettrages, sinistres, banques.
#>

$ProjectDir = "D:\Robot\ASSURPROD"
$SqlFile    = "$ProjectDir\migration_scripts\reset_business_data.sql"

Set-Location $ProjectDir

Write-Host ""
Write-Host "========================================================" -ForegroundColor Red
Write-Host "  RESET + RE-IMPORT COMPLET — AssurCore DATA_REEL      " -ForegroundColor Red
Write-Host "========================================================" -ForegroundColor Red
Write-Host ""
Write-Host "  Ce script va :" -ForegroundColor White
Write-Host "  ✓  Supprimer toutes les données métier importées" -ForegroundColor Yellow
Write-Host "  ✓  Conserver : config entreprise, utilisateurs, profils" -ForegroundColor Green
Write-Host "  ✓  Re-importer depuis DATA_REEL_22-05-2026 (données complètes)" -ForegroundColor Green
Write-Host ""
Write-Host "  Appuyez sur ENTRÉE pour continuer ou Ctrl+C pour annuler..." -ForegroundColor White
Read-Host

# ── 1. Reset SQL ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "▶  Étape 1/2 — Reset des données métier en base..." -ForegroundColor Cyan
Write-Host ""

$tStart = [datetime]::Now
docker cp $SqlFile assurcore_db:/tmp/reset_business_data.sql
docker exec assurcore_db psql -U odoo -d assurcore_db -f /tmp/reset_business_data.sql -v ON_ERROR_STOP=1
$exitCode = $LASTEXITCODE
$elapsed  = [math]::Round(([datetime]::Now - $tStart).TotalSeconds, 1)

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "  ✗  Erreur lors du reset SQL (code $exitCode)" -ForegroundColor Red
    Write-Host "     Vérifiez les erreurs ci-dessus avant de continuer." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  ✓  Reset terminé en ${elapsed}s — base nettoyée" -ForegroundColor Green
Write-Host ""

# ── 2. Re-import complet depuis DATA_REEL ────────────────────────────────────
Write-Host "▶  Étape 2/2 — Re-import complet depuis DATA_REEL..." -ForegroundColor Cyan
Write-Host ""

& "$ProjectDir\run_etl_phase2.ps1" -Steps "all"
