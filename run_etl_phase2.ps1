#Requires -Version 5.1
<#
.SYNOPSIS
    ETL Phase 2 — Migration complète depuis DATA_REEL vers AssurCore Odoo

.DESCRIPTION
    Lance le script import_assurcore_v2.py avec les données réelles (DATA_REEL_22-05-2026)
    qui contient :
      - 96  sinistres    (vs 1  dans DATA_ASS.txt)
      - 22930 factures   (vs 15738)
      - 21773 règlements (vs 15767)
      - 22844 lettrages  (vs 16561)
      - 4678  clients    (vs 3726)

    Le script est idempotent : les enregistrements déjà importés sont ignorés (skip).

.PARAMETER DryRun
    Simule l'import sans écrire en base. Affiche les statistiques attendues.

.PARAMETER Steps
    Étapes à exécuter (défaut: all).
    Valeurs possibles : risques,codes,clients,banques,factures,reglements,lettrage,sinistres,experts
    Exemple : -Steps "sinistres" pour migrer uniquement les sinistres

.EXAMPLES
    .\run_etl_phase2.ps1 -DryRun          # Simulation complète
    .\run_etl_phase2.ps1                   # Import réel complet
    .\run_etl_phase2.ps1 -Steps sinistres  # Sinistres uniquement
#>

param(
    [switch]$DryRun,
    [string]$Steps = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n▶  $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "   ✓  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "   ⚠  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "   ✗  $msg" -ForegroundColor Red ; exit 1 }

$ProjectDir  = "D:\Robot\ASSURPROD"
$ScriptPath  = "$ProjectDir\migration_scripts\import_assurcore_v2.py"
$DataPath    = "$ProjectDir\DATA_REEL_22-05-2026\DATA_REEL"

Set-Location $ProjectDir

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ETL Phase 2 — AssurCore Migration DATA_REEL          " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Vérifications préalables ──────────────────────────────────────────────
Write-Step "Vérifications préalables..."

if (-not (Test-Path $ScriptPath)) {
    Write-Fail "Script ETL introuvable : $ScriptPath"
}
Write-OK "Script ETL trouvé"

if (-not (Test-Path $DataPath)) {
    Write-Fail "Répertoire de données introuvable : $DataPath"
}
$tsvCount = (Get-ChildItem "$DataPath\*.tsv").Count
Write-OK "Répertoire DATA_REEL trouvé ($tsvCount fichiers .tsv)"

# ── 2. Vérifier Python ───────────────────────────────────────────────────────
Write-Step "Vérification de Python..."
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $pythonCmd = $cmd
            Write-OK "Python trouvé : $ver ($cmd)"
            break
        }
    } catch { }
}
if (-not $pythonCmd) {
    Write-Fail "Python 3 introuvable. Installez Python depuis https://www.python.org/downloads/"
}

# ── 3. Vérifier la connexion Odoo ────────────────────────────────────────────
Write-Step "Vérification de la connexion Odoo (localhost:8071)..."
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8071/web/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-OK "Odoo répond sur http://localhost:8071"
    }
} catch {
    Write-Fail "Odoo ne répond pas sur localhost:8071. Démarrez les containers avec : docker compose -p assurcore up -d"
}

# ── 4. Afficher le résumé des données à importer ────────────────────────────
Write-Step "Résumé des données à importer depuis DATA_REEL..."
Write-Host ""
Write-Host "   Table              Lignes    " -ForegroundColor White
Write-Host "   ─────────────────────────── " -ForegroundColor DarkGray
$tables = @("PR_SINISTRE", "PR_FACTURE", "PR_REGELEMENT", "PR_REG_FACTURE", "PR_CLIENT", "PR_RISQUE", "PR_BANQUE")
foreach ($t in $tables) {
    $f = "$DataPath\${t}_DATA_TABLE.tsv"
    if (Test-Path $f) {
        $lines = (Get-Content $f -TotalCount 1000000 | Measure-Object -Line).Lines - 1
        Write-Host ("   {0,-22} {1,6} enregistrements" -f $t, $lines) -ForegroundColor Gray
    }
}
Write-Host ""

if ($DryRun) {
    Write-Warn "MODE DRY-RUN activé — aucune écriture en base"
} else {
    Write-Host "   ⚡  Import RÉEL — les données seront écrites dans assurcore_db" -ForegroundColor Yellow
    Write-Host "   ℹ   Le script est idempotent : les doublons sont ignorés automatiquement." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Appuyez sur ENTRÉE pour continuer ou Ctrl+C pour annuler..." -ForegroundColor White
    Read-Host
}

# ── 5. Lancer le script ETL ──────────────────────────────────────────────────
Write-Step "Lancement de l'ETL Phase 2 (étapes : $Steps)..."
Write-Host "   (Durée estimée : 10 à 30 minutes selon le volume)" -ForegroundColor DarkGray
Write-Host ""

$etlArgs = @(
    $ScriptPath,
    "--file", $DataPath,
    "--steps", $Steps
)
if ($DryRun) {
    $etlArgs += "--dry-run"
}

$logFile = "$ProjectDir\migration_scripts\etl_phase2_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
Write-Host "   Log : $logFile" -ForegroundColor DarkGray
Write-Host ""

# Lancer avec affichage en temps réel ET sauvegarde dans le log
& $pythonCmd @etlArgs 2>&1 | Tee-Object -FilePath $logFile

$exitCode = $LASTEXITCODE

# ── 6. Résumé final ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan

if ($exitCode -eq 0) {
    Write-Host "  ✓  ETL Phase 2 terminé avec succès !" -ForegroundColor Green
} else {
    Write-Host "  ⚠  ETL terminé avec des avertissements (code $exitCode)" -ForegroundColor Yellow
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Log complet sauvegardé : $logFile" -ForegroundColor White
Write-Host ""
Write-Host "  Vérification dans Odoo :" -ForegroundColor White
Write-Host "    Assurances > Sinistres    (96 sinistres attendus)" -ForegroundColor Gray
Write-Host "    Assurances > Quittances   (22930 factures attendues)" -ForegroundColor Gray
Write-Host "    Assurances > Règlements   (21773 règlements attendus)" -ForegroundColor Gray
Write-Host ""
