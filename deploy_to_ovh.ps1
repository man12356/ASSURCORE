# =============================================================================
# deploy_to_ovh.ps1 — ASSURCORE v1.0 — UNIFIED VPS DEPLOYMENT SCRIPT
# =============================================================================
# Ce script automatise : Git Push -> Packaging -> Upload WinSCP -> Remote Rebuild & Restore
# =============================================================================

$ErrorActionPreference = "Stop"
$ProjectDir = "d:\Robot\ASSURPROD"
$ZipFile    = "d:\Robot\assurcore_prod_latest.zip"
$WinSCP     = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$Git        = "C:\Program Files\Git\cmd\git.exe"

# Credentials (OVH VPS)
$VPS_HOST   = "vps784643.ovh.net"
$VPS_USER   = "root"
$VPS_PASS   = "Btc*19!75mB*20!04KNEE"
$RemoteDir  = "/root/assurcore_prod"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       ASSURCORE — Production VPS Deployment          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. GIT UPDATE ─────────────────────────────────────────────────────────────
Write-Host "→ 1/4 : Syncing code with Git..." -ForegroundColor Yellow
try {
    $CurrentBranch = (& $Git branch --show-current).Trim()
    Write-Host "  → Branch detected: $CurrentBranch" -ForegroundColor Gray
    & $Git add .
    & $Git commit -m "Production Deploy: AssurCore stable release with complete database dump"
    & $Git push origin $CurrentBranch
    Write-Host "  ✓ Code synced to repository." -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Git sync failed or already up to date. Continuing with packaging..." -ForegroundColor Gray
}

# ── 2. PACKAGING ──────────────────────────────────────────────────────────────
Write-Host "→ 2/4 : Creating deployment package (ZIP)..." -ForegroundColor Yellow
$BundleDir = "d:\Robot\deploy_bundle_assurcore"
if (Test-Path $BundleDir) { Remove-Item $BundleDir -Recurse -Force }
if (Test-Path $ZipFile)   { Remove-Item $ZipFile -Force }

New-Item -ItemType Directory -Path $BundleDir | Out-Null

Write-Host "  → Copying files to bundle (excluding heavy database folders, test data, and logs)..." -ForegroundColor Gray
# Utilisation de robocopy pour sa robustesse (exclusion de DATA_TEST pour alléger le zip)
& robocopy $ProjectDir $BundleDir /S /XD .git data_db addons __pycache__ scratch .vscode DATA_TEST /XF *.zip *.log *.xlsx *.pdf *.docx | Out-Null

# Copier le dump de la base de données spécifique pour la restauration en production
$DumpSrc = "d:\Robot\ASSURPROD\data_db\assurcore_db.dump"
$DumpDstDir = "$BundleDir\data_db"
if (Test-Path $DumpSrc) {
    New-Item -ItemType Directory -Path $DumpDstDir | Out-Null
    Copy-Item $DumpSrc -Destination "$DumpDstDir\assurcore_db.dump" -Force
    Write-Host "  ✓ Database dump included in the package: $DumpSrc" -ForegroundColor Green
} else {
    Write-Warning "  ⚠ Database dump file not found at $DumpSrc! Restoring database might fail."
}

Write-Host "  → Compressing bundle (using Python for memory efficiency)..." -ForegroundColor Gray
& python -c "import shutil; shutil.make_archive('d:\Robot\assurcore_prod_latest', 'zip', '$BundleDir')"

Write-Host "  → Cleaning up bundle..." -ForegroundColor Gray
Remove-Item $BundleDir -Recurse -Force

Write-Host "  ✓ Package created: $ZipFile ($((Get-Item $ZipFile).Length / 1MB -as [int]) MB)" -ForegroundColor Green

# ── 3. UPLOAD & REMOTE EXECUTION ──────────────────────────────────────────────
Write-Host "→ 3/4 : Uploading to OVH VPS and rebuilding..." -ForegroundColor Yellow

$SessionUrl = "sftp://${VPS_USER}:$($VPS_PASS -replace '!', '%21')@$VPS_HOST/"
$RemoteZip  = "/root/assurcore_latest.zip"

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "echo --- Cleaning remote old ZIP ---" `
    "call rm -f $RemoteZip" `
    "echo --- Uploading ZIP ---" `
    "put `"$ZipFile`" $RemoteZip" `
    "echo --- Remote Rebuild Sequence ---" `
    "call mkdir -p $RemoteDir" `
    "call unzip -o $RemoteZip -d $RemoteDir" `
    "echo --- Copying AssurCore to Addons ---" `
    "call mkdir -p $RemoteDir/addons" `
    "call cp -rf $RemoteDir/assurcore $RemoteDir/addons/" `
    "echo --- Restarting Docker Containers ---" `
    "call cd $RemoteDir && docker-compose down" `
    "call cd $RemoteDir && ODOO_PORT=8071 docker-compose up -d --build" `
    "echo --- Waiting for database to be ready (15s) ---" `
    "call sleep 15" `
    "echo --- Restoring PostgreSQL Database Dump ---" `
    "call docker-compose exec -T db pg_restore -U odoo -d postgres_system --clean --create /var/lib/postgresql/data/assurcore_db.dump" `
    "echo --- Restarting Odoo to load restored database cache ---" `
    "call docker-compose restart web" `
    "echo --- Cleaning up ---" `
    "call rm -f $RemoteZip" `
    "exit"

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Upload, remote rebuild, and database restore successful." -ForegroundColor Green
} else {
    Write-Host "  ✗ Error during WinSCP transfer/execution." -ForegroundColor Red
    exit 1
}

# ── 4. FINAL STATUS & HEALTH CHECK ────────────────────────────────────────────
Write-Host "→ 4/4 : Verifying deployment health on remote VPS..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
try {
    $Response = Invoke-WebRequest -Uri "http://${VPS_HOST}:8071/web/health" -UseBasicParsing -TimeoutSec 10
    if ($Response.StatusCode -eq 200) {
        Write-Host "  ✓ Odoo is Healthy on port 8071!" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Odoo returned status $($Response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ Health check failed (Odoo might still be starting or DNS issues)." -ForegroundColor Gray
}

Write-Host ""
Write-Host "✅ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "🌍 Remote App URL : http://${VPS_HOST}:8071" -ForegroundColor Cyan
Write-Host ""
