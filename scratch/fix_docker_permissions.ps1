# fix_docker_permissions.ps1
# A exécuter en tant qu'Administrateur (clic droit > Exécuter en tant qu'administrateur)
# Ce script :
#   1. Ajoute l'utilisateur courant au groupe docker-users
#   2. Corrige les permissions sur .docker\config.json
#   3. Lance docker compose up -d pour AssurCore

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "=== Fix Docker Permissions pour: $currentUser ===" -ForegroundColor Cyan

# 1. Ajouter au groupe docker-users
Write-Host "`n[1/4] Ajout au groupe docker-users..." -ForegroundColor Yellow
try {
    net localgroup docker-users "$currentUser" /add
    Write-Host "  ✓ Utilisateur ajouté au groupe docker-users" -ForegroundColor Green
} catch {
    Write-Host "  ! Erreur: $_" -ForegroundColor Red
}

# 2. Corriger les permissions sur .docker\config.json
Write-Host "`n[2/4] Correction des permissions config.json..." -ForegroundColor Yellow
$configPath = "$env:USERPROFILE\.docker\config.json"
if (Test-Path $configPath) {
    try {
        $acl = Get-Acl $configPath
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $currentUser, "FullControl", "Allow"
        )
        $acl.SetAccessRule($rule)
        Set-Acl $configPath $acl
        Write-Host "  ✓ Permissions corrigées sur $configPath" -ForegroundColor Green
    } catch {
        Write-Host "  ! Erreur ACL: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  - config.json n'existe pas, création d'un fichier vide..." -ForegroundColor Gray
    New-Item -ItemType Directory -Force "$env:USERPROFILE\.docker" | Out-Null
    '{}' | Out-File "$env:USERPROFILE\.docker\config.json" -Encoding UTF8
    Write-Host "  ✓ Fichier créé" -ForegroundColor Green
}

# 3. Vérifier que Docker Desktop est lancé
Write-Host "`n[3/4] Vérification de Docker Desktop..." -ForegroundColor Yellow
$dockerProc = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProc) {
    Write-Host "  - Docker Desktop n'est pas lancé, démarrage..." -ForegroundColor Gray
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "  ✓ Docker Desktop lancé, attente 60 secondes..." -ForegroundColor Green
    Start-Sleep -Seconds 60
} else {
    Write-Host "  ✓ Docker Desktop est déjà actif (PID: $($dockerProc.Id))" -ForegroundColor Green
    Start-Sleep -Seconds 10
}

# 4. Démarrer les containers AssurCore
Write-Host "`n[4/4] Démarrage des containers AssurCore..." -ForegroundColor Yellow
Set-Location "d:\Robot\ASSURPROD"
docker compose -p assurcore up -d 2>&1

# Vérification finale
Write-Host "`n=== État final des containers ===" -ForegroundColor Cyan
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host "`n✓ Terminé ! Odoo accessible sur http://localhost:8071" -ForegroundColor Green
Write-Host "  (attendre ~2 minutes pour le démarrage complet d'Odoo)" -ForegroundColor Gray
