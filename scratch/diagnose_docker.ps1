# diagnose_docker.ps1
# Ce script diagnostique l'état des conteneurs Odoo et PostgreSQL pour AssurCore.
# Il écrit les résultats dans d:\Robot\ASSURPROD\scratch\docker_diagnosis.txt.

$Cwd = "d:\Robot\ASSURPROD"
$DiagFile = "$Cwd\scratch\docker_diagnosis.txt"

Write-Host "Diagnostic de l'état Docker en cours..." -ForegroundColor Cyan

# Nettoyer l'ancien diagnostic
if (Test-Path $DiagFile) { Remove-Item $DiagFile -Force }

# Commencer l'écriture
"============================================================" | Out-File $DiagFile -Append
"  DIAGNOSTIC DOCKER ASSURCORE" | Out-File $DiagFile -Append
"  Date : $(Get-Date)" | Out-File $DiagFile -Append
"============================================================" | Out-File $DiagFile -Append
"" | Out-File $DiagFile -Append

"--- [1] Liste des conteneurs du projet 'assurcore' ---" | Out-File $DiagFile -Append
docker compose -p assurcore ps --all 2>&1 | Out-File $DiagFile -Append
"" | Out-File $DiagFile -Append

"--- [2] État général de Docker ---" | Out-File $DiagFile -Append
docker info --format '{{json .}}' 2>$null | Out-File $DiagFile -Append
if ($LASTEXITCODE -ne 0) {
    "Docker Info standard non disponible, fallback :" | Out-File $DiagFile -Append
    docker info 2>&1 | Out-File $DiagFile -Append
}
"" | Out-File $DiagFile -Append

"--- [3] Ports écoutés sur la machine hôte (findstr 807) ---" | Out-File $DiagFile -Append
netstat -ano | findstr "807" 2>&1 | Out-File $DiagFile -Append
"" | Out-File $DiagFile -Append

"--- [4] Logs récents du conteneur Odoo (web) ---" | Out-File $DiagFile -Append
docker compose -p assurcore logs --tail 100 web 2>&1 | Out-File $DiagFile -Append
"" | Out-File $DiagFile -Append

"--- [5] Logs récents du conteneur PostgreSQL (db) ---" | Out-File $DiagFile -Append
docker compose -p assurcore logs --tail 100 db 2>&1 | Out-File $DiagFile -Append
"" | Out-File $DiagFile -Append

Write-Host "Fait ! Le fichier de diagnostic a été généré : $DiagFile" -ForegroundColor Green
