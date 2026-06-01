#Requires -Version 5.1
<#
.SYNOPSIS
    Mise à jour du module AssurCore (EVO01 — Workflow OCR)

.DESCRIPTION
    1. Synchronise assurcore/ → addons/assurcore/
    2. Arrete le container web
    3. Lance odoo -u assurcore --stop-after-init dans un container temporaire
    4. Redémarre le container web
    5. Affiche les derniers logs pour confirmer le succès

.NOTES
    ✅ PAS besoin de mode Administrateur
    Répertoire de travail : D:\Robot\ASSURPROD
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Couleurs ────────────────────────────────────────────────────────────────
function Write-Step  { param($msg) Write-Host "`n▶  $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "   ✓  $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "   ⚠  $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "   ✗  $msg" -ForegroundColor Red ; exit 1 }

# ── Répertoire de travail ────────────────────────────────────────────────────
$ProjectDir = "D:\Robot\ASSURPROD"
Set-Location $ProjectDir
Write-OK "Répertoire : $ProjectDir"

# ── 1. Vérifier que Docker Desktop est lancé ─────────────────────────────────
Write-Step "Vérification Docker Desktop..."
try {
    $null = docker info 2>&1
    Write-OK "Docker Desktop est actif"
} catch {
    Write-Fail "Docker Desktop ne répond pas. Lancez Docker Desktop puis réessayez."
}

# ── 2. Vérifier que le container DB est démarré ────────────────────────────
Write-Step "Vérification du container DB AssurCore..."
$dbStatus = docker inspect --format='{{.State.Status}}' assurcore_db 2>&1

if ($dbStatus -ne "running") {
    Write-Warn "Container DB arrêté — démarrage de la stack complète..."
    docker compose -p assurcore up -d
    Write-Host "   Attente démarrage PostgreSQL (30s)..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 30
} else {
    Write-OK "DB : $dbStatus"
}

# ── 3. Synchroniser assurcore/ → addons/assurcore/ ──────────────────────────
Write-Step "Synchronisation assurcore/ → addons/assurcore/..."
$src  = Join-Path $ProjectDir "assurcore"
$dest = Join-Path $ProjectDir "addons\assurcore"

if (-not (Test-Path $src)) {
    Write-Fail "Dossier source introuvable : $src"
}

$roboArgs = @($src, $dest, "/MIR", "/XD", "__pycache__", "/NFL", "/NDL", "/NJH", "/NJS")
robocopy @roboArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Fail "Robocopy a échoué (code $LASTEXITCODE)"
}
Write-OK "Synchronisation terminée"

# ── 4. Arrêter le container web (libérer le port 8069) ──────────────────────
Write-Step "Arrêt du container web (libération du port 8069)..."
$webStatus = docker inspect --format='{{.State.Status}}' assurcore_web 2>&1
if ($webStatus -eq "running") {
    docker stop assurcore_web | Out-Null
    Write-OK "Container web arrêté"
} else {
    Write-OK "Container web déjà arrêté"
}

# ── 5. Mise à jour dans un container temporaire ────────────────────────────
Write-Step "Mise à jour du module assurcore (container temporaire)..."
Write-Host "   (Cette étape prend 2 à 5 minutes — soyez patient)" -ForegroundColor DarkGray

$updateArgs = @(
    "run", "--rm",
    "--network", "assurcore_network",
    "-v", "${ProjectDir}\addons:/mnt/extra-addons",
    "-v", "${ProjectDir}\config:/etc/odoo",
    "-v", "assurcore_filestore:/var/lib/odoo",
    "-e", "HOST=db",
    "-e", "PORT=5432",
    "-e", "USER=odoo",
    "-e", "PASSWORD=odoo",
    "odoo:17.0",
    "odoo",
    "--config=/etc/odoo/odoo.conf",
    "-d", "assurcore_db",
    "-u", "assurcore",
    "--stop-after-init"
)

docker @updateArgs
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Warn "odoo --stop-after-init a retourné le code $exitCode"
    Write-Host "   Des erreurs Python/XML ont peut-être été détectées (voir logs ci-dessus)." -ForegroundColor Yellow
} else {
    Write-OK "Module mis à jour avec succès (code 0)"
}

# ── 6. Redémarrer le container web ──────────────────────────────────────────
Write-Step "Redémarrage du container web Odoo..."
docker start assurcore_web | Out-Null
Write-OK "Container web redémarré"

# ── 7. Attendre qu'Odoo soit prêt ───────────────────────────────────────────
Write-Step "Attente de la disponibilite d'Odoo (health check)..."
$maxWait   = 120
$waited    = 0
$odooReady = $false
$odooPort  = "8071"

while ($waited -lt $maxWait) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$odooPort/web/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $odooReady = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 5
    $waited += 5
    Write-Host "   ... ${waited}s / ${maxWait}s" -ForegroundColor DarkGray
}

if ($odooReady) {
    Write-OK "Odoo repond sur http://localhost:$odooPort"
} else {
    Write-Warn "Odoo ne repond pas encore (timeout ${maxWait}s) — verifiez les logs"
}

# ── 8. Afficher les 30 dernières lignes de logs ──────────────────────────────
Write-Step "Derniers logs du container Odoo (30 lignes) :"
Write-Host "---------------------------------------------------------" -ForegroundColor DarkGray
docker logs assurcore_web --tail=30
Write-Host "---------------------------------------------------------" -ForegroundColor DarkGray

# ── Résumé final ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  MISE A JOUR TERMINEE — AssurCore EVO01 (Workflow OCR)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Interface Odoo : http://localhost:$odooPort/web" -ForegroundColor White
Write-Host "  Login          : admin / admin" -ForegroundColor White
Write-Host ""
Write-Host "  Test EVO01 :" -ForegroundColor White
Write-Host "    1. Assurances > Polices > ouvrir une police 'Brouillon OCR'" -ForegroundColor Gray
Write-Host "    2. Cliquer 'Valider les donnees OCR' > wizard popup" -ForegroundColor Gray
Write-Host "    3. Ou : Assurances > Importation OCR > Documents OCR" -ForegroundColor Gray
Write-Host ""
if ($exitCode -ne 0) {
    Write-Host "  ATTENTION : Des erreurs ont ete detectees lors de la mise a jour." -ForegroundColor Yellow
    Write-Host "  Copiez les logs ci-dessus et partagez-les pour analyse." -ForegroundColor Yellow
}
Write-Host ""
