#Requires -Version 5.1
<#
.SYNOPSIS
    Mise à jour rapide des clients via SQL direct dans PostgreSQL.
    Beaucoup plus rapide que XML-RPC (10 sec vs 40 min).
#>

$ProjectDir = "D:\Robot\ASSURPROD"
$SqlFile    = "$ProjectDir\migration_scripts\update_clients.sql"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Mise à jour clients — SQL direct PostgreSQL           " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Copier le SQL dans le container
Write-Host "▶  Copie du script SQL dans le container..." -ForegroundColor Cyan
$t = Get-Date
docker cp $SqlFile assurcore_db:/tmp/update_clients.sql
Write-Host ("   ✓  Copié en {0:N1}s" -f (Get-Date - $t).TotalSeconds) -ForegroundColor Green

# Exécuter le SQL
Write-Host "▶  Exécution des 4678 UPDATE (transaction unique)..." -ForegroundColor Cyan
$t = Get-Date
docker exec assurcore_db psql -U odoo -d assurcore_db -f /tmp/update_clients.sql -v ON_ERROR_STOP=1 2>&1 | Select-Object -Last 10
$exitCode = $LASTEXITCODE
$elapsed  = (Get-Date - $t).TotalSeconds

if ($exitCode -eq 0) {
    Write-Host ("   ✓  Mise à jour terminée en {0:N1}s !" -f $elapsed) -ForegroundColor Green
} else {
    Write-Host ("   ⚠  Code de sortie : $exitCode — vérifiez les erreurs ci-dessus") -ForegroundColor Yellow
}

# Vérification rapide
Write-Host "▶  Vérification : clients avec CIN renseigné..." -ForegroundColor Cyan
docker exec assurcore_db psql -U odoo -d assurcore_db -c "SELECT COUNT(*) AS clients_avec_cin FROM res_partner WHERE cin IS NOT NULL AND cin != '';"
docker exec assurcore_db psql -U odoo -d assurcore_db -c "SELECT COUNT(*) AS clients_avec_mf FROM res_partner WHERE matricule_fiscal IS NOT NULL AND matricule_fiscal != '';"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Clients mis à jour ! Vérifiez dans Odoo :" -ForegroundColor Cyan
Write-Host "  Contacts → ouvrir un client → onglet Assurance" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
