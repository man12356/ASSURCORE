# ==============================================================================
#  FIX DÉFINITIF — Docker Desktop doit pointer sur le disque virtuel déplacé en D:
#
#  Contexte : ext4.vhdx déplacé manuellement vers
#      D:\Docker\wsl\data\DockerDesktopWSL\main\ext4.vhdx
#  → l'enregistrement WSL de la distro "docker-desktop" pointe encore sur C:
#  → le démon ne démarre plus (npipe dockerDesktopLinuxEngine introuvable).
#
#  Principe de la correction (persistant après reboot ET mises à jour) :
#   1. Arrêt propre de Docker Desktop et de WSL
#   2. Dés-enregistrement de la distro docker-desktop (ne supprime PAS le vhdx en D:)
#   3. Ré-enregistrement SUR PLACE vers le vhdx de D: (wsl --import-in-place)
#      → WSL inscrit le nouveau chemin dans le registre (HKCU\...\Lxss\{GUID}\BasePath)
#   4. Alignement du paramètre « Disk image location » de Docker Desktop sur D:
#      pour que les mises à jour ne recréent jamais le disque sur C:
#   5. Redémarrage + vérification
#
#  Exécution : PowerShell (pas besoin d'admin pour WSL, admin conseillé pour tuer
#  les services Docker) :   powershell -ExecutionPolicy Bypass -File .\FIX_DOCKER_VHDX_DISQUE_D.ps1
# ==============================================================================

$ErrorActionPreference = 'Stop'
$VHDX   = 'D:\Docker\wsl\data\DockerDesktopWSL\main\ext4.vhdx'
$DATA   = 'D:\Docker\wsl\data'          # valeur a mettre dans Docker Desktop
$DESKTOP = "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"

function Step($msg) { Write-Host "`n=== $msg" -ForegroundColor Cyan }

# ── 0. Pré-vérifications ──────────────────────────────────────────────────────
Step "Vérification du disque virtuel déplacé"
if (-not (Test-Path $VHDX)) {
    Write-Host "INTROUVABLE : $VHDX" -ForegroundColor Red
    Write-Host "Adaptez la variable `$VHDX en tête de script au chemin réel." -ForegroundColor Red
    exit 1
}
$size = [math]::Round((Get-Item $VHDX).Length / 1GB, 2)
Write-Host "OK : $VHDX ($size Go)"

# ── 1. Arrêt propre ───────────────────────────────────────────────────────────
Step "Arrêt de Docker Desktop et de WSL"
Get-Process 'Docker Desktop','com.docker.backend','com.docker.build','vpnkit' `
    -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 3
wsl --shutdown
Start-Sleep 2

# ── 2. État actuel des distros ────────────────────────────────────────────────
Step "Distros WSL enregistrées (avant)"
wsl -l -v

# ── 3. Ré-enregistrement de docker-desktop vers le vhdx de D: ─────────────────
Step "Ré-enregistrement de la distro docker-desktop sur $VHDX"
$dist = (wsl -l -q) -replace "`0",''   # nettoie l'encodage UTF-16 de wsl.exe
if ($dist -contains 'docker-desktop') {
    Write-Host "Dés-enregistrement de l'ancienne entrée (le vhdx de D: n'est pas touché)…"
    wsl --unregister docker-desktop | Out-Null
}
# Ancien schéma à 2 distros (Docker Desktop < 4.30) : nettoyer aussi -data si présent
if ($dist -contains 'docker-desktop-data') {
    Write-Host "Ancien schéma détecté : dés-enregistrement de docker-desktop-data…"
    wsl --unregister docker-desktop-data | Out-Null
}
Write-Host "Import sur place (aucune copie, le vhdx reste en D:)…"
wsl --import-in-place docker-desktop $VHDX
if ($LASTEXITCODE -ne 0) {
    Write-Host "ÉCHEC import-in-place. Vérifiez la version de WSL : wsl --version (>= 1.0 requis ; sinon : wsl --update)" -ForegroundColor Red
    exit 1
}
Write-Host "Distro docker-desktop ré-enregistrée → BasePath = D:" -ForegroundColor Green

# ── 4. Aligner la config Docker Desktop (persistance aux mises à jour) ────────
Step "Alignement du paramètre Disk image location de Docker Desktop"
$patched = $false
foreach ($cfg in @("$Env:APPDATA\Docker\settings-store.json",
                   "$Env:APPDATA\Docker\settings.json")) {
    if (Test-Path $cfg) {
        $json = Get-Content $cfg -Raw | ConvertFrom-Json
        foreach ($key in 'DataFolder','dataFolder','DiskImageLocation','diskImageLocation') {
            if ($json.PSObject.Properties.Name -contains $key) {
                $json.$key = $DATA
                $patched = $true
            }
        }
        if ($patched) {
            $json | ConvertTo-Json -Depth 10 | Set-Content $cfg -Encoding UTF8
            Write-Host "Patché : $cfg → $DATA" -ForegroundColor Green
            break
        }
    }
}
if (-not $patched) {
    Write-Host "Clé non trouvée dans les fichiers de config — faites-le UNE FOIS via l'interface :" -ForegroundColor Yellow
    Write-Host "  Docker Desktop → Settings → Resources → Advanced → Disk image location = $DATA" -ForegroundColor Yellow
    Write-Host "  (comme le vhdx y est déjà, aucun déplacement ne sera refait)" -ForegroundColor Yellow
}

# ── 5. Redémarrage et vérification ───────────────────────────────────────────
Step "Démarrage de Docker Desktop (silencieux, barre système)"
Start-Process $DESKTOP
Write-Host "Attente du démon Docker…"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 5
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
}
if ($ok) {
    Step "SUCCÈS — le démon répond"
    wsl -l -v
    docker info --format 'Images: {{.Images}} | Containers: {{.Containers}} | Root: {{.DockerRootDir}}'
    Write-Host "`nPreuve que D: est bien utilisé : la date du vhdx doit venir de changer :"
    Get-Item $VHDX | Select-Object FullName, Length, LastWriteTime
    Write-Host "`nVous pouvez maintenant lancer :" -ForegroundColor Green
    Write-Host "  cd D:\Robot\ASSURPROD ; docker compose up -d" -ForegroundColor Green
} else {
    Write-Host "Le démon ne répond pas après 5 min — envoyez le contenu de :" -ForegroundColor Red
    Write-Host "  %LOCALAPPDATA%\Docker\log\host\*.log (les 50 dernières lignes du plus récent)" -ForegroundColor Red
}
