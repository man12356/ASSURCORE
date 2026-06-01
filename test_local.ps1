<#
.SYNOPSIS
    Test local AssurCore — Synchronise et met a jour le module sans toucher aux donnees.

.PARAMETER FullReset
    Reinstalle le module depuis zero (supprime et recree assurcore_db).

.PARAMETER LogsOnly
    Affiche les logs Odoo sans faire de mise a jour.

.EXAMPLE
    .\test_local.ps1
    .\test_local.ps1 -FullReset
    .\test_local.ps1 -LogsOnly
#>

[CmdletBinding()]
param(
    [switch] $FullReset,
    [switch] $LogsOnly
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
# NOTE : PAS de Set-StrictMode ni ErrorActionPreference=Stop
# Docker ecrit des warnings sur stderr ce qui ferait planter le script

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$DB_NAME    = 'assurcore_db'
$ODOO_PORT  = 8071
$MODULE_SRC = Join-Path $SCRIPT_DIR 'assurcore'
$MODULE_DST = Join-Path $SCRIPT_DIR 'addons\assurcore'

Set-Location $SCRIPT_DIR

function Write-Step { param($M) Write-Host "`n>> $M" -ForegroundColor Magenta }
function Write-OK   { param($M) Write-Host "   OK  $M" -ForegroundColor Green  }
function Write-Info { param($M) Write-Host "   ..  $M" -ForegroundColor Cyan   }
function Write-Warn { param($M) Write-Host "   !!  $M" -ForegroundColor Yellow }
function Write-Err  { param($M) Write-Host "   XX  $M" -ForegroundColor Red    }

# Wrapper docker compose qui avale les warnings stderr sans planter
function dc {
    param([string[]]$Args)
    # Rediriger stderr vers stdout pour eviter que PowerShell traite les warnings comme erreurs
    & docker compose -p assurcore @Args 2>&1 | Where-Object {
        # Filtrer les lignes de warning connues (version obsolete)
        $_ -notmatch 'attribute.*version.*obsolete|please remove it'
    } | ForEach-Object { Write-Host "  $($_)" -ForegroundColor DarkGray }
}

# Meme chose mais capture la sortie plutot que l'afficher
function dc-silent {
    param([string[]]$Args)
    & docker compose -p assurcore @Args 2>&1 | Out-Null
}

Write-Host ""
Write-Host "+============================================+" -ForegroundColor Blue
Write-Host "|   AssurCore - Test Local (mise a jour)    |" -ForegroundColor Blue
Write-Host "+============================================+" -ForegroundColor Blue

# ── 1. Verification Docker ────────────────────────────────────────────────────
Write-Step "1/6 - Verification Docker"
$dockerOk = $false
try {
    $v = & docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerOk = $true
        Write-OK $v
    }
} catch { }

if (-not $dockerOk) {
    Write-Err "Docker Desktop n'est pas accessible. Demarrez-le et relancez."
    exit 1
}

if ($LogsOnly) {
    Write-Info "Logs Odoo (Ctrl+C pour quitter)..."
    & docker logs -f assurcore_web 2>&1
    exit 0
}

# ── 2. Synchronisation des fichiers ──────────────────────────────────────────
Write-Step "2/6 - Synchronisation assurcore/ -> addons/assurcore/"

if (-not (Test-Path $MODULE_DST)) {
    New-Item -ItemType Directory -Path $MODULE_DST -Force | Out-Null
}

$srcFiles = Get-ChildItem -Path $MODULE_SRC -Recurse -File
$updated = 0; $added = 0
foreach ($f in $srcFiles) {
    $rel    = $f.FullName.Substring($MODULE_SRC.Length)
    $dst    = Join-Path $MODULE_DST $rel
    $dstDir = Split-Path $dst -Parent
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
    if (-not (Test-Path $dst)) {
        Copy-Item $f.FullName $dst -Force; $added++
    } elseif ($f.LastWriteTime -gt (Get-Item $dst).LastWriteTime) {
        Copy-Item $f.FullName $dst -Force; $updated++
    }
}
Write-OK "$updated fichier(s) mis a jour, $added nouveau(x)"

# ── 3. Detection des containers (via docker ps, plus fiable) ─────────────────
Write-Step "3/6 - Etat des containers"

# docker ps retourne les noms des containers en cours, simple et robuste
$running = & docker ps --format '{{.Names}}' 2>&1
$dbUp    = ($running | Where-Object { $_ -match 'assurcore_db'  }).Count -gt 0
$webUp   = ($running | Where-Object { $_ -match 'assurcore_web' }).Count -gt 0

if ($dbUp) {
    Write-OK "assurcore_db  : en cours d'execution"
} else {
    Write-Warn "assurcore_db non demarre — lancement..."
    & docker compose -p assurcore up -d db 2>&1 | Out-Null
    Start-Sleep -Seconds 15
    Write-OK "assurcore_db demarre"
}

if ($webUp) {
    Write-OK "assurcore_web : en cours d'execution"
} else {
    Write-Warn "assurcore_web non demarre — lancement..."
    & docker compose -p assurcore up -d web 2>&1 | Out-Null
    Start-Sleep -Seconds 20
    Write-OK "assurcore_web demarre"
}

# ── 4a. Reset complet (optionnel) ────────────────────────────────────────────
$skipUpgrade = $false
if ($FullReset) {
    Write-Step "RESET - Suppression et reinstallation de $DB_NAME"
    Write-Warn "Toutes les donnees de test locales seront perdues !"
    $confirm = Read-Host "   Confirmer ? (oui)"
    if ($confirm -ne 'oui') { Write-Info "Annule."; exit 0 }

    Write-Info "Arret du container web..."
    & docker stop assurcore_web 2>&1 | Out-Null

    Write-Info "Suppression de $DB_NAME..."
    & docker exec assurcore_db dropdb -U odoo --if-exists $DB_NAME 2>&1 | Out-Null

    Write-Info "Creation de $DB_NAME..."
    & docker exec assurcore_db createdb -U odoo $DB_NAME 2>&1 | Out-Null

    Write-Info "Installation initiale du module assurcore..."
    Write-Info "(prend 2 a 5 minutes - normal)"
    & docker run --rm `
        --network assurcore_network `
        -v "${SCRIPT_DIR}\addons:/mnt/extra-addons" `
        -v "${SCRIPT_DIR}\config:/etc/odoo" `
        -e HOST=assurcore_db -e USER=odoo -e PASSWORD=odoo `
        odoo:17.0 `
        odoo -d $DB_NAME -i assurcore `
             --stop-after-init `
             --config=/etc/odoo/odoo.conf `
             --without-demo=all 2>&1 | Tee-Object -Variable installLog

    $ok = ($installLog | Where-Object { $_ -match 'Modules loaded' }).Count -gt 0
    if ($ok) {
        Write-OK "Module installe avec succes"
    } else {
        $errs = $installLog | Where-Object { $_ -match 'ERROR|CRITICAL|Traceback' }
        if ($errs) {
            Write-Err "Erreurs detectees :"
            $errs | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        }
        Write-Warn "Verifiez les erreurs ci-dessus avant de continuer."
    }

    Write-Info "Redemarrage du container web..."
    & docker start assurcore_web 2>&1 | Out-Null
    Start-Sleep -Seconds 10
    # Sauter directement au health check (pas de goto en PowerShell — on utilise un flag)
    $skipUpgrade = $true
}

# ── 4b. Mise a jour du module (mode normal) ───────────────────────────────────
if (-not $skipUpgrade) {
Write-Step "4/6 - Mise a jour assurcore (-u assurcore --stop-after-init)"
Write-Info "Arret temporaire du container web (les donnees restent intactes)..."
& docker stop assurcore_web 2>&1 | Out-Null
Write-OK "Container web arrete"

Write-Info "Lancement de la mise a jour (30 a 90 secondes)..."
Write-Info "(openpyxl installe a la volee dans le container temporaire)"
Write-Host ""

# Utiliser 'docker run' directement avec sh -c pour installer openpyxl d'abord
$upgradeLog = & docker run --rm `
    --network assurcore_network `
    -v "${SCRIPT_DIR}\addons:/mnt/extra-addons" `
    -v "${SCRIPT_DIR}\config:/etc/odoo" `
    -e HOST=assurcore_db `
    -e USER=odoo `
    -e PASSWORD=odoo `
    odoo:17.0 `
    sh -c "pip install --quiet --user openpyxl && odoo -d $DB_NAME -u assurcore --stop-after-init --config=/etc/odoo/odoo.conf" 2>&1

# Afficher les lignes importantes
$upgradeLog | Where-Object {
    $_ -match 'ERROR|WARNING|INFO.*assurcore|INFO.*ocr|INFO.*training|Modules loaded|CRITICAL|Traceback'
} | ForEach-Object {
    $color = if ($_ -match 'ERROR|CRITICAL|Traceback') { 'Red' }
             elseif ($_ -match 'WARNING') { 'Yellow' }
             else { 'Cyan' }
    Write-Host "  $_" -ForegroundColor $color
}

Write-Host ""

# Analyser le resultat
# $isLoaded doit matcher "N modules loaded" APRES le chargement d'assurcore (>1 module)
$hasErrors   = ($upgradeLog | Where-Object { $_ -match 'CRITICAL|Traceback|SyntaxError|ImportError|ModuleNotFoundError' }).Count -gt 0
$isLoaded    = ($upgradeLog | Where-Object { $_ -match 'odoo\.modules\.loading.*\d{2,} modules loaded' }).Count -gt 0
$hasOcrLines = ($upgradeLog | Where-Object { $_ -match 'ocr_training|ocr_classify|insurance_ocr' }).Count -gt 0

if ($hasErrors) {
    Write-Err "La mise a jour a echoue. Details des erreurs :"
    $upgradeLog | Where-Object { $_ -match 'CRITICAL|Traceback|ModuleNotFoundError|ImportError' } | Select-Object -First 20 |
        ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host ""
    Write-Warn "Odoo NE sera PAS redemarre pour proteger la base."
    Write-Host "  -> Consultez tous les logs : .\test_local.ps1 -LogsOnly" -ForegroundColor Yellow
    Write-Info "Redemarrage du container web (version precedente)..."
    & docker start assurcore_web 2>&1 | Out-Null
    exit 1
} elseif ($isLoaded) {
    Write-OK "Mise a jour reussie — module charge sans erreur critique"
    if ($hasOcrLines) { Write-OK "Tables OCR training detectees dans les logs" }
} else {
    Write-Warn "Fin de mise a jour — verifiez les logs si doute (.\test_local.ps1 -LogsOnly)"
}

# ── 5. Redemarrage container web ─────────────────────────────────────────────
Write-Step "5/6 - Redemarrage du container web"
& docker start assurcore_web 2>&1 | Out-Null
Write-OK "Container assurcore_web redemarre"
} # fin if -not $skipUpgrade

# ── 6. Health check ───────────────────────────────────────────────────────────
Write-Step "6/6 - Verification sante Odoo"

$healthUrl = "http://localhost:$ODOO_PORT/web/health"
$elapsed   = 0
$ready     = $false

Write-Info "Attente sur $healthUrl (max 120s)..."
while ($elapsed -lt 120) {
    try {
        $r = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 4 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
    $elapsed += 5
    Write-Host "   . ${elapsed}s" -ForegroundColor DarkGray
}

Write-Host ""
if ($ready) {
    Write-Host ""
    Write-Host "+====================================================+" -ForegroundColor Green
    Write-Host "|  TEST LOCAL REUSSI                                 |" -ForegroundColor Green
    Write-Host "+----------------------------------------------------+" -ForegroundColor Green
    Write-Host "|  URL    : http://localhost:$ODOO_PORT              |" -ForegroundColor Green
    Write-Host "|  Login  : admin / admin                           |" -ForegroundColor Green
    Write-Host "|  Pret en : ${elapsed}s                                 |" -ForegroundColor Green
    Write-Host "+====================================================+" -ForegroundColor Green
    Write-Host ""
    Write-Host "A tester dans l'interface :" -ForegroundColor White
    Write-Host "  1. Importation OCR -> Documents OCR (colonne Type coloree)" -ForegroundColor Cyan
    Write-Host "  2. Importation OCR -> Apprentissage OCR (table de regles)" -ForegroundColor Cyan
    Write-Host "  3. Creer un parser doc_type='autre' -> bouton 'Classifier'" -ForegroundColor Cyan
    Write-Host "  4. Wizard 2 etapes -> changer type -> verifier apprentissage" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Warn "Odoo ne repond pas apres ${elapsed}s."
    Write-Host "  -> Logs : .\test_local.ps1 -LogsOnly" -ForegroundColor Yellow
    Write-Host "  -> Statut : docker ps | findstr assurcore" -ForegroundColor Yellow
}
