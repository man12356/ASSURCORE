@echo off
:: ============================================================
::  fix_docker_admin.bat — A exécuter en tant qu'Administrateur
:: ============================================================
echo.
echo ========================================
echo  FIX DOCKER PERMISSIONS - AssurCore
echo ========================================
echo.

:: 1. Ajouter LENOVO au groupe docker-users
echo [1/4] Ajout de LENOVO au groupe docker-users...
net localgroup docker-users "DESKTOP-7H3RN7O\lenovo" /add 2>NUL
if %errorlevel%==0 (
    echo      OK - Utilisateur ajoute au groupe docker-users
) else (
    echo      INFO - Deja membre ou groupe inexistant
)

:: 2. Supprimer le config.json bloque
echo.
echo [2/4] Correction du fichier config.json...
takeown /f "C:\Users\LENOVO\.docker\config.json" /a 2>NUL
icacls "C:\Users\LENOVO\.docker\config.json" /grant "DESKTOP-7H3RN7O\lenovo:F" /c 2>NUL
icacls "C:\Users\LENOVO\.docker" /grant "DESKTOP-7H3RN7O\lenovo:F" /t /c 2>NUL
echo      OK - Permissions corrigees

:: 3. Verifier Docker Desktop
echo.
echo [3/4] Verification de Docker Desktop...
tasklist | find /i "Docker Desktop.exe" >NUL 2>&1
if %errorlevel%==0 (
    echo      OK - Docker Desktop est actif
) else (
    echo      Demarrage de Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo      Attente 60 secondes...
    timeout /t 60 /nobreak
)

:: 4. Demarrer AssurCore
echo.
echo [4/4] Demarrage des containers AssurCore...
cd /d "d:\Robot\ASSURPROD"
docker compose -p assurcore up -d

echo.
echo ========================================
echo  ETAT DES CONTAINERS :
echo ========================================
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo TERMINE ! Odoo : http://localhost:8071
echo.
pause
