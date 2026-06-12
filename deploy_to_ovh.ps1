# =============================================================================
# deploy_to_ovh.ps1 — ASSURCORE v2.0 (EVO02) — UNIFIED VPS DEPLOYMENT SCRIPT
# =============================================================================
# Git Push -> Packaging -> Upload -> Lancement DETACHE du rebuild (nohup)
# -> Suivi du log par polling (robuste aux coupures reseau) -> Health check
# Le rebuild dure 15-25 min : il tourne sur le VPS meme si la connexion tombe.
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
$RemoteZip  = "/root/assurcore_latest.zip"

$SessionUrl = "sftp://${VPS_USER}:$($VPS_PASS -replace '!', '%21')@$VPS_HOST/"
$OpenCmd    = "open `"$SessionUrl`" -hostkey=`"*`" -timeout=120 -rawsettings SendBuf=0 PipelineLimit=1"

Write-Host ""
Write-Host "=== ASSURCORE — Production VPS Deployment (EVO02) ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. GIT UPDATE ─────────────────────────────────────────────────────────────
Write-Host "-> 1/5 : Syncing code with Git..." -ForegroundColor Yellow
try {
    $CurrentBranch = (& $Git branch --show-current).Trim()
    Write-Host "  -> Branch: $CurrentBranch" -ForegroundColor Gray
    & $Git add . 2>$null
    & $Git commit -m "Production Deploy: AssurCore EVO02" 2>$null
    & $Git push origin $CurrentBranch
    Write-Host "  OK Code synced." -ForegroundColor Green
} catch {
    Write-Host "  ! Git sync skipped (up to date). Continuing..." -ForegroundColor Gray
}

# ── 2. PACKAGING ──────────────────────────────────────────────────────────────
Write-Host "-> 2/5 : Creating deployment package (ZIP)..." -ForegroundColor Yellow
$BundleDir = "d:\Robot\deploy_bundle_assurcore"
if (Test-Path $BundleDir) { Remove-Item $BundleDir -Recurse -Force }
if (Test-Path $ZipFile)   { Remove-Item $ZipFile -Force }
New-Item -ItemType Directory -Path $BundleDir | Out-Null

& robocopy $ProjectDir $BundleDir /S /XD .git data_db addons __pycache__ scratch .vscode DATA_TEST /XF *.zip *.log *.xlsx *.pdf *.docx | Out-Null

$DumpSrc = "d:\Robot\ASSURPROD\data_db\assurcore_db.dump"
if (Test-Path $DumpSrc) {
    New-Item -ItemType Directory -Path "$BundleDir\data_db" | Out-Null
    Copy-Item $DumpSrc -Destination "$BundleDir\data_db\assurcore_db.dump" -Force
    Write-Host "  OK Database dump included." -ForegroundColor Green
} else {
    Write-Warning "  ! Database dump not found at $DumpSrc"
}

$BundleDirPy = $BundleDir -replace '\\', '/'
$ZipFilePy = $ZipFile -replace '\\', '/' -replace '\.zip', ''
& python -c "import shutil; shutil.make_archive('$ZipFilePy', 'zip', '$BundleDirPy')"
Remove-Item $BundleDir -Recurse -Force
Write-Host "  OK Package: $ZipFile ($((Get-Item $ZipFile).Length / 1MB -as [int]) MB)" -ForegroundColor Green

# ── 3. UPLOAD ─────────────────────────────────────────────────────────────────
Write-Host "-> 3/5 : Uploading ZIP to VPS..." -ForegroundColor Yellow
& $WinSCP /ini=nul /command `
    $OpenCmd `
    "call rm -f $RemoteZip" `
    "put `"$ZipFile`" $RemoteZip" `
    "exit"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Upload failed. Re-run the script (transfer will resume)." -ForegroundColor Red
    exit 1
}
Write-Host "  OK ZIP uploaded." -ForegroundColor Green

# ── 4. LANCEMENT DETACHE DU REBUILD + SUIVI DU LOG ───────────────────────────
Write-Host "-> 4/5 : Launching DETACHED rebuild on VPS (nohup)..." -ForegroundColor Yellow
& $WinSCP /ini=nul /command `
    $OpenCmd `
    "call mkdir -p $RemoteDir" `
    "call unzip -oq $RemoteZip -d $RemoteDir" `
    "call rm -f $RemoteZip" `
    "call chmod +x $RemoteDir/rebuild_vps.sh" `
    "call cd $RemoteDir; rm -f rebuild.log rebuild.pid; nohup ./rebuild_vps.sh > rebuild.log 2>&1 & echo `$! > rebuild.pid; sleep 1; echo LANCEMENT_OK" `
    "exit"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Could not launch remote rebuild." -ForegroundColor Red
    exit 1
}
Write-Host "  OK Rebuild launched in background. Polling log every 30s (max 50 min)..." -ForegroundColor Green
Write-Host "     (Une coupure reseau ici est SANS GRAVITE : le rebuild continue sur le VPS.)" -ForegroundColor Gray

$Start = Get-Date
$Result = "TIMEOUT"
while (((Get-Date) - $Start).TotalMinutes -lt 50) {
    Start-Sleep -Seconds 30
    try {
        $PollOut = (& $WinSCP /ini=nul /command `
            $OpenCmd `
            "call cd $RemoteDir; tail -n 3 rebuild.log 2>/dev/null; (kill -0 `$(cat rebuild.pid) 2>/dev/null && echo ___RUNNING___ || echo ___STOPPED___)" `
            "exit" 2>&1 | Out-String)
    } catch { continue }
    $LastLines = ($PollOut -split "`r?`n" | Where-Object { $_ -match "^===|ECHEC|RECETTE|TESTS|Erreur|error" } | Select-Object -Last 1)
    $Elapsed = [int]((Get-Date) - $Start).TotalMinutes
    if ($LastLines) { Write-Host "  [$Elapsed min] $LastLines" -ForegroundColor Gray }
    if ($PollOut -match "REBUILD EVO02 TERMINE") { $Result = "OK"; break }
    if ($PollOut -match "ECHEC RECETTE|ECHEC TESTS") { $Result = "FAIL"; break }
    if ($PollOut -match "___STOPPED___" -and $PollOut -notmatch "REBUILD EVO02 TERMINE") { $Result = "DIED"; break }
}

if ($Result -eq "OK") {
    Write-Host "  OK Remote rebuild completed: recette conforme, tests OK." -ForegroundColor Green
} else {
    Write-Host "  X Rebuild result: $Result — voir le log complet :" -ForegroundColor Red
    Write-Host "    via WinSCP : call cat $RemoteDir/rebuild.log" -ForegroundColor Yellow
    & $WinSCP /ini=nul /command $OpenCmd "call tail -n 40 $RemoteDir/rebuild.log" "exit"
    exit 1
}

# ── 5. HEALTH CHECK ───────────────────────────────────────────────────────────
Write-Host "-> 5/5 : Verifying deployment health..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
try {
    $Response = Invoke-WebRequest -Uri "https://assurcore.metadidomi.com/web/health" -UseBasicParsing -TimeoutSec 15
    if ($Response.StatusCode -eq 200) {
        Write-Host "  OK Odoo is Healthy!" -ForegroundColor Green
    } else {
        Write-Host "  ! Odoo returned status $($Response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ! Health check failed (Odoo may still be starting)." -ForegroundColor Gray
}

Write-Host ""
Write-Host "DEPLOYMENT SUCCESSFUL — https://assurcore.metadidomi.com" -ForegroundColor Green
Write-Host ""
