#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Déplace Docker Desktop (WSL2) de C: vers D: pour libérer de l'espace.
    À lancer en PowerShell Administrateur.
#>

$TargetDir = "D:\Docker\wsl"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Déplacement Docker C: → D:                           " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Arrêt complet de WSL et Docker
Write-Host "▶  Arrêt de WSL et Docker..." -ForegroundColor Cyan
Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "dockerd" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
wsl --shutdown
Start-Sleep -Seconds 2
Write-Host "   ✓  WSL arrêté" -ForegroundColor Green

# 2. Créer les dossiers cibles
Write-Host "▶  Création des dossiers cibles sur D:..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$TargetDir\data"    | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\distro"  | Out-Null
Write-Host "   ✓  Dossiers créés : $TargetDir" -ForegroundColor Green

# 3. Lister les distros WSL Docker
Write-Host ""
Write-Host "▶  Distros WSL détectées :" -ForegroundColor Cyan
wsl --list --verbose
Write-Host ""

# 4. Exporter et réimporter docker-desktop-data (le plus volumineux)
$distro1 = "docker-desktop-data"
$tar1 = "D:\docker-desktop-data.tar"

Write-Host "▶  Export de '$distro1' vers $tar1 ..." -ForegroundColor Cyan
Write-Host "   (peut prendre 5-15 minutes selon la taille)" -ForegroundColor DarkGray
$t = Get-Date
wsl --export $distro1 $tar1
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ⚠  Export échoué ou distro absente — passage au suivant" -ForegroundColor Yellow
} else {
    $elapsed = [math]::Round((Get-Date - $t).TotalSeconds, 1)
    Write-Host "   ✓  Export terminé en ${elapsed}s" -ForegroundColor Green

    Write-Host "▶  Suppression ancienne distro '$distro1'..." -ForegroundColor Cyan
    wsl --unregister $distro1

    Write-Host "▶  Import vers $TargetDir\data ..." -ForegroundColor Cyan
    wsl --import $distro1 "$TargetDir\data" $tar1 --version 2
    Write-Host "   ✓  '$distro1' importée sur D:" -ForegroundColor Green

    Write-Host "▶  Suppression du tar temporaire..." -ForegroundColor Cyan
    Remove-Item $tar1 -Force
    Write-Host "   ✓  Tar supprimé" -ForegroundColor Green
}

# 5. Exporter et réimporter docker-desktop (distro système)
$distro2 = "docker-desktop"
$tar2 = "D:\docker-desktop.tar"

Write-Host ""
Write-Host "▶  Export de '$distro2' vers $tar2 ..." -ForegroundColor Cyan
$t = Get-Date
wsl --export $distro2 $tar2
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ⚠  Export échoué ou distro absente" -ForegroundColor Yellow
} else {
    $elapsed = [math]::Round((Get-Date - $t).TotalSeconds, 1)
    Write-Host "   ✓  Export terminé en ${elapsed}s" -ForegroundColor Green

    Write-Host "▶  Suppression ancienne distro '$distro2'..." -ForegroundColor Cyan
    wsl --unregister $distro2

    Write-Host "▶  Import vers $TargetDir\distro ..." -ForegroundColor Cyan
    wsl --import $distro2 "$TargetDir\distro" $tar2 --version 2
    Write-Host "   ✓  '$distro2' importée sur D:" -ForegroundColor Green

    Write-Host "▶  Suppression du tar temporaire..." -ForegroundColor Cyan
    Remove-Item $tar2 -Force
    Write-Host "   ✓  Tar supprimé" -ForegroundColor Green
}

# 6. Vérification finale
Write-Host ""
Write-Host "▶  Vérification des distros WSL :" -ForegroundColor Cyan
wsl --list --verbose

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  ✓  Déplacement terminé !                             " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Étapes suivantes :" -ForegroundColor White
Write-Host "  1. Lancez Docker Desktop normalement" -ForegroundColor Gray
Write-Host "  2. Vérifiez Settings > Resources > Disk image location" -ForegroundColor Gray
Write-Host "     (devrait pointer vers D:\Docker\wsl\data)" -ForegroundColor Gray
Write-Host "  3. Relancez : docker compose -p assurcore up -d" -ForegroundColor Gray
Write-Host ""

# Optionnel : libérer aussi le cache WSL sur C:
$wslCache = "$env:LOCALAPPDATA\Docker\wsl"
if (Test-Path $wslCache) {
    $size = [math]::Round((Get-ChildItem $wslCache -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB, 2)
    Write-Host "  ℹ  Ancien dossier Docker sur C: : $wslCache ($size GB)" -ForegroundColor DarkGray
    Write-Host "     Vous pouvez le supprimer manuellement si Docker fonctionne bien." -ForegroundColor DarkGray
}
Write-Host ""
