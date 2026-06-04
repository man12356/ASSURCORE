<#
.SYNOPSIS
    Lance l'ETL import_assurcore.py contre le VPS de production.
    Importe uniquement les etapes manquantes (operations par defaut).

.PARAMETER Steps
    Etapes a importer : all | operations | settlements | claims | policies
    Defaut : operations (les autres etapes sont deja migrees)

.PARAMETER DryRun
    Parse et affiche les stats sans ecrire dans Odoo.

.EXAMPLE
    .\run_etl_prod.ps1                    # importe les operations
    .\run_etl_prod.ps1 -Steps all         # reimporte tout (idempotent)
    .\run_etl_prod.ps1 -DryRun            # verification sans ecriture
#>

[CmdletBinding()]
param(
    [string] $Steps   = 'operations',
    [switch] $DryRun
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

$SCRIPT_DIR   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ETL_SCRIPT   = Join-Path $SCRIPT_DIR 'migration_scripts\import_assurcore.py'
$DATA_FILE    = Join-Path $SCRIPT_DIR 'DATA_ASS.txt'
$PATCHED      = Join-Path $SCRIPT_DIR 'migration_scripts\_import_prod_patched.py'

# ── Configuration Production ──────────────────────────────────────────────────
$PROD_URL  = 'https://assurcore.metadidomi.com'
$PROD_DB   = 'assurcore_db'
$PROD_USER = 'admin'
$PROD_PASS = 'admin'

Write-Host ""
Write-Host "+================================================+" -ForegroundColor Blue
Write-Host "|   AssurCore ETL — Import Production VPS        |" -ForegroundColor Blue
Write-Host "+================================================+" -ForegroundColor Blue
Write-Host "  URL     : $PROD_URL" -ForegroundColor Cyan
Write-Host "  Base    : $PROD_DB" -ForegroundColor Cyan
Write-Host "  Etapes  : $Steps" -ForegroundColor Cyan
Write-Host "  DryRun  : $($DryRun.IsPresent)" -ForegroundColor Cyan
Write-Host ""

# ── Verification des prerequis ────────────────────────────────────────────────
if (-not (Test-Path $ETL_SCRIPT)) {
    Write-Host "XX  Script ETL introuvable : $ETL_SCRIPT" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $DATA_FILE)) {
    Write-Host "XX  Fichier DATA_ASS.txt introuvable : $DATA_FILE" -ForegroundColor Red
    Write-Host "    Assurez-vous que DATA_ASS.txt est dans $SCRIPT_DIR" -ForegroundColor Yellow
    exit 1
}

# ── Patch du script : remplacer les constantes de connexion ──────────────────
Write-Host ">> Preparation du script patche pour production..." -ForegroundColor Magenta
$content = Get-Content $ETL_SCRIPT -Raw -Encoding UTF8

$content = $content -replace "ODOO_URL\s*=\s*'[^']*'",   "ODOO_URL      = '$PROD_URL'"
$content = $content -replace 'ODOO_URL\s*=\s*"[^"]*"',   "ODOO_URL      = `"$PROD_URL`""
$content = $content -replace "ODOO_DB\s*=\s*'[^']*'",    "ODOO_DB       = '$PROD_DB'"
$content = $content -replace "ODOO_USER\s*=\s*'[^']*'",  "ODOO_USER     = '$PROD_USER'"
$content = $content -replace "ODOO_PASSWORD\s*=\s*'[^']*'", "ODOO_PASSWORD = '$PROD_PASS'"

[System.IO.File]::WriteAllText($PATCHED, $content, [System.Text.Encoding]::UTF8)
Write-Host "   OK  Script patche : $PATCHED" -ForegroundColor Green

# ── Lancement de l'ETL ────────────────────────────────────────────────────────
Write-Host ""
Write-Host ">> Lancement de l'ETL (etapes : $Steps)..." -ForegroundColor Magenta
Write-Host "   Patience — l'import peut prendre plusieurs minutes." -ForegroundColor Cyan
Write-Host ""

$args_etl = @(
    $PATCHED,
    '--steps', $Steps,
    '--file',  $DATA_FILE
)
if ($DryRun) { $args_etl += '--dry-run' }

& python @args_etl

$exitCode = $LASTEXITCODE
Write-Host ""

if ($exitCode -eq 0) {
    Write-Host "+================================================+" -ForegroundColor Green
    Write-Host "|  ETL TERMINE AVEC SUCCES                       |" -ForegroundColor Green
    Write-Host "+------------------------------------------------+" -ForegroundColor Green
    Write-Host "|  Verifiez dans Odoo :                          |" -ForegroundColor Green
    Write-Host "|  Etat Mouvement Clients primes                 |" -ForegroundColor Green
    Write-Host "|  -> Opérations contractuelles                  |" -ForegroundColor Green
    Write-Host "+================================================+" -ForegroundColor Green
} else {
    Write-Host "XX  ETL termine avec des erreurs (code $exitCode)." -ForegroundColor Red
    Write-Host "    Consultez import_assurcore.log pour le detail." -ForegroundColor Yellow
}

# Nettoyage du fichier patche
Remove-Item $PATCHED -ErrorAction SilentlyContinue
