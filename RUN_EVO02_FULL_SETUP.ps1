# ==============================================================================
#  RUN_EVO02_FULL_SETUP.ps1 — Remise en route complète, en un seul lancement :
#    1. WSL à jour + nettoyage du vhdx vide en D:
#    2. Configuration du « Disk image location » de Docker Desktop sur D:
#       AVANT son démarrage (définitif : survit aux reboots et mises à jour)
#    3. Démarrage silencieux de Docker Desktop + attente du démon
#    4. docker compose up + attente PostgreSQL
#    5. Restauration de la base depuis data_db\assurcore_db.dump
#    6. Mise à jour du module assurcore + exécution des tests EVO02
#       (sortie enregistrée dans evo02_test_result.log → à envoyer à Claude)
#    7. Redémarrage d'Odoo en mode normal
#
#  Usage :  powershell -ExecutionPolicy Bypass -File .\RUN_EVO02_FULL_SETUP.ps1
# ==============================================================================

$ErrorActionPreference = 'Continue'
$PROJ    = 'D:\Robot\ASSURPROD'
$DATA    = 'D:\Docker\wsl\data'
$OLDVHDX = "$DATA\DockerDesktopWSL"
$DESKTOP = "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
$DB      = 'assurcore_db'
$LOG     = "$PROJ\evo02_test_result.log"

function Step($m){ Write-Host "`n========== $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host $m -ForegroundColor Green }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Fail($m){ Write-Host $m -ForegroundColor Red }

Set-Location $PROJ

# ── 1. WSL à jour + état des lieux ───────────────────────────────────────────
Step "1/7 WSL : mise à jour et nettoyage"
wsl --update 2>$null | Out-Null
wsl --shutdown
Get-Process 'Docker Desktop','com.docker.backend' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 3

# Y a-t-il encore un GROS vhdx sur C: (l'original) ?
$cWsl = "$Env:LOCALAPPDATA\Docker\wsl"
$bigC = $null
if (Test-Path $cWsl) {
    $bigC = Get-ChildItem $cWsl -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -gt 1GB } | Sort-Object Length -Descending |
            Select-Object -First 1
}
if ($bigC) {
    Ok "Disque d'origine retrouvé sur C: : $($bigC.FullName) ($([math]::Round($bigC.Length/1GB,2)) Go)"
    Ok "→ il sera migré vers D: par Docker Desktop (étape 2) ; rien à restaurer."
} else {
    Warn "Pas de gros vhdx sur C: → la base sera restaurée depuis data_db\assurcore_db.dump (étape 5)."
}

# Supprimer le vhdx VIDE de D: (uniquement s'il fait moins de 500 Mo)
if (Test-Path "$OLDVHDX\main\ext4.vhdx") {
    $sz = (Get-Item "$OLDVHDX\main\ext4.vhdx").Length
    if ($sz -lt 500MB) {
        Remove-Item $OLDVHDX -Recurse -Force -ErrorAction SilentlyContinue
        Ok "vhdx vide de D: supprimé ($([math]::Round($sz/1MB)) Mo) — Docker va recréer proprement."
    } else {
        Warn "vhdx de D: > 500 Mo : conservé par prudence."
    }
}
New-Item -ItemType Directory -Force -Path $DATA | Out-Null

# ── 2. Pointer Docker Desktop sur D: AVANT démarrage ─────────────────────────
Step "2/7 Configuration Disk image location → $DATA"
$patched = $false
foreach ($cfg in @("$Env:APPDATA\Docker\settings-store.json",
                   "$Env:APPDATA\Docker\settings.json")) {
    if (-not (Test-Path $cfg)) { continue }
    try {
        $json = Get-Content $cfg -Raw | ConvertFrom-Json
        foreach ($key in 'DataFolder','dataFolder','DiskImageLocation','diskImageLocation','customWslDistroDir') {
            if ($json.PSObject.Properties.Name -contains $key) {
                $json.$key = $DATA; $patched = $true
            }
        }
        if (-not $patched) {
            # la clé n'existe pas encore : on l'ajoute (nom moderne)
            $json | Add-Member -NotePropertyName 'DataFolder' -NotePropertyValue $DATA -Force
            $patched = $true
        }
        $json | ConvertTo-Json -Depth 10 | Set-Content $cfg -Encoding UTF8
        Ok "Patché : $cfg"
        break
    } catch { Warn "Impossible de patcher $cfg : $_" }
}
if (-not $patched) {
    Warn "Config non patchée — après démarrage, réglez UNE FOIS dans Docker Desktop :"
    Warn "Settings → Resources → Advanced → Disk image location = $DATA  (Apply & Restart)"
}

# ── 3. Démarrage silencieux de Docker Desktop ────────────────────────────────
Step "3/7 Démarrage de Docker Desktop (icône barre système)"
Start-Process $DESKTOP
$ok = $false
for ($i = 0; $i -lt 72; $i++) {
    Start-Sleep 5
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    if ($i % 6 -eq 5) { Write-Host "  …attente du démon ($((($i+1)*5)) s)" }
}
if (-not $ok) { Fail "Démon Docker injoignable après 6 min. Ouvrez Docker Desktop et regardez l'erreur affichée."; exit 1 }
Ok "Démon Docker opérationnel."
wsl -l -v

# ── 4. Stack AssurCore ───────────────────────────────────────────────────────
Step "4/7 docker compose up (téléchargement des images si nécessaire)"
docker compose up -d
if ($LASTEXITCODE -ne 0) { Fail "compose up en échec — sortie ci-dessus."; exit 1 }

Write-Host "Attente de PostgreSQL…"
$pgok = $false
for ($i = 0; $i -lt 36; $i++) {
    Start-Sleep 5
    docker compose exec db pg_isready -U odoo -d postgres_system 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $pgok = $true; break }
}
if (-not $pgok) { Fail "PostgreSQL ne répond pas — docker compose logs db"; exit 1 }
Ok "PostgreSQL prêt."

# ── 5. Restauration de la base si nécessaire ─────────────────────────────────
Step "5/7 Base $DB : restauration depuis le dump si absente/vide"
docker compose exec db psql -U odoo -d postgres_system -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" 2>$null | Tee-Object -Variable dbExists | Out-Null
$needRestore = $true
if ("$dbExists".Trim() -eq '1') {
    $nbTables = (docker compose exec db psql -U odoo -d $DB -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>$null)
    if ([int]("$nbTables".Trim()) -gt 50) {
        Ok "Base $DB déjà peuplée ($("$nbTables".Trim()) tables) — pas de restauration."
        $needRestore = $false
    }
}
if ($needRestore) {
    Write-Host "Restauration de data_db\assurcore_db.dump…"
    docker compose stop web | Out-Null
    docker compose exec db psql -U odoo -d postgres_system -c "DROP DATABASE IF EXISTS $DB" | Out-Null
    docker compose exec db psql -U odoo -d postgres_system -c "CREATE DATABASE $DB OWNER odoo" | Out-Null
    docker compose exec db pg_restore -U odoo -d $DB --no-owner /backups/assurcore_db.dump
    if ($LASTEXITCODE -ne 0) { Warn "pg_restore a signalé des avertissements (souvent bénins : owners/ACL)." }
    Ok "Base restaurée."
}

# ── 6. Mise à jour EVO02 + tests ─────────────────────────────────────────────
Step "6/7 Upgrade module assurcore + tests EVO02 (log → $LOG)"
docker compose stop web | Out-Null
docker compose run --rm web odoo -c /etc/odoo/odoo.conf -d $DB -u assurcore `
    --test-tags evo02 --stop-after-init --log-level=info 2>&1 | Tee-Object -FilePath $LOG
$testExit = $LASTEXITCODE

$failures = Select-String -Path $LOG -Pattern 'FAIL|ERROR.*test_evo02|CRITICAL|Traceback' -SimpleMatch:$false
if ($testExit -eq 0 -and -not $failures) {
    Ok "TESTS EVO02 : SUCCÈS (aucune erreur détectée dans le log)"
} else {
    Fail "Des erreurs sont présentes — envoyez le fichier evo02_test_result.log à Claude :"
    $failures | Select-Object -First 10 | ForEach-Object { Write-Host "  $($_.Line)" }
}

# ── 7. Redémarrage normal ────────────────────────────────────────────────────
Step "7/7 Redémarrage d'Odoo"
docker compose up -d web | Out-Null
Start-Sleep 10
docker compose ps
Ok "`nTerminé. Interface : http://localhost:8071  (base : $DB)"
Ok "À vérifier visuellement : menu Qualité des données · bouton Graphe sur une opération · onglet Règlements (lettrage)."
Write-Host "`nEmplacement disque Docker (preuve D:) :"
Get-ChildItem "$DATA" -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue |
    Select-Object FullName, @{n='Go';e={[math]::Round($_.Length/1GB,2)}}, LastWriteTime
