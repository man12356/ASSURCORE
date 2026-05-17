<#
.SYNOPSIS
    Déploiement local AssurCore — Odoo 17.0 + PostgreSQL 15 sous Windows.

.DESCRIPTION
    Script PowerShell de déploiement intelligent pour Windows (Docker Desktop).
    Détecte automatiquement un port libre, synchronise le module assurcore,
    lance les containers et vérifie que Odoo répond.

.PARAMETER Reset
    Arrête les containers et supprime les volumes (REPART DE ZÉRO).
    ATTENTION : efface toutes les données PostgreSQL.

.PARAMETER Stop
    Arrête proprement les containers sans supprimer les données.

.PARAMETER Logs
    Affiche les logs Odoo en temps réel après le démarrage.

.PARAMETER PortStart
    Premier port à tester (défaut : 8069).

.EXAMPLE
    .\deploy_local.ps1
    .\deploy_local.ps1 -Logs
    .\deploy_local.ps1 -Reset
    .\deploy_local.ps1 -Stop

.NOTES
    Pré-requis : Docker Desktop for Windows installé et démarré.
    PowerShell 5.1+ ou PowerShell 7+ (recommandé).
#>

[CmdletBinding()]
param(
    [switch] $Reset,
    [switch] $Stop,
    [switch] $Logs,
    [int]    $PortStart = 8069
)

# ── Encodage UTF-8 pour les emojis et accents ────────────────────────────────
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ── Strict mode ──────────────────────────────────────────────────────────────
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Constantes ───────────────────────────────────────────────────────────────
$PORT_END       = $PortStart + 10      # Teste jusqu'à 10 ports
$COMPOSE_FILE   = 'docker-compose.yml'
$MODULE_SRC     = 'assurcore'
$ADDONS_DIR     = 'addons'
$DATA_DIR       = 'data_db'
$CONFIG_DIR     = 'config'
$PROJECT_NAME   = 'assurcore'
$HEALTH_TIMEOUT = 300                  # Secondes d'attente Odoo (Docker Desktop = lent)

# ── Répertoire du script (base pour tous les chemins relatifs) ────────────────
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

# ══════════════════════════════════════════════════════════════════════════════
#  Fonctions d'affichage coloré
# ══════════════════════════════════════════════════════════════════════════════

function Write-Info    { param([string]$Msg) Write-Host "  i  $Msg" -ForegroundColor Cyan }
function Write-Success { param([string]$Msg) Write-Host "  OK $Msg" -ForegroundColor Green }
function Write-Warn    { param([string]$Msg) Write-Host "  !  $Msg" -ForegroundColor Yellow }
function Write-Err     { param([string]$Msg) Write-Host "  X  $Msg" -ForegroundColor Red }
function Write-Step    { param([string]$Msg)
    Write-Host ""
    Write-Host "-- $Msg " -ForegroundColor Magenta -NoNewline
    Write-Host ("-" * [Math]::Max(1, 50 - $Msg.Length)) -ForegroundColor DarkGray
}

function Write-Banner {
    Write-Host ""
    Write-Host "  +==========================================+" -ForegroundColor Blue
    Write-Host "  |   AssurCore -- Deploiement Local        |" -ForegroundColor Blue
    Write-Host "  |   Odoo 17.0 + PostgreSQL 15             |" -ForegroundColor Blue
    Write-Host "  |   Script PowerShell (Windows)           |" -ForegroundColor Blue
    Write-Host "  +==========================================+" -ForegroundColor Blue
    Write-Host ""
}

function Write-SuccessBanner {
    param([string]$Port)
    Write-Host ""
    Write-Host "  +================================================================+" -ForegroundColor Green
    Write-Host "  |                                                                |" -ForegroundColor Green
    Write-Host "  |   Deploiement reussi !                                         |" -ForegroundColor Green
    Write-Host "  |                                                                |" -ForegroundColor Green
    Write-Host ("  |   Odoo AssurCore  :  http://localhost:{0,-34}|" -f "$Port") -ForegroundColor Green
    Write-Host "  |   PostgreSQL      :  Port interne uniquement (securise)       |" -ForegroundColor Green
    Write-Host "  |                                                                |" -ForegroundColor Green
    Write-Host "  |   Identifiants    :  admin / admin                            |" -ForegroundColor Green
    Write-Host "  |   Base de donnees :  assurcore_db (a creer via l'interface)   |" -ForegroundColor Green
    Write-Host "  |                                                                |" -ForegroundColor Green
    Write-Host "  +================================================================+" -ForegroundColor Green
    Write-Host ""
}

# ══════════════════════════════════════════════════════════════════════════════
#  Fonction : Tester si un port TCP local est libre
# ══════════════════════════════════════════════════════════════════════════════

function Test-PortFree {
    param([int]$Port)
    <#
    .SYNOPSIS
        Retourne $true si le port est LIBRE, $false s'il est OCCUPÉ.
    .DESCRIPTION
        Utilise System.Net.Sockets.TcpClient pour tenter une connexion.
        Aucun outil externe requis — fonctionne sur toutes les versions Windows.
    #>
    $tcpClient = $null
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        # ConnectAsync avec timeout court (300ms) pour ne pas bloquer
        $connectTask = $tcpClient.ConnectAsync('127.0.0.1', $Port)
        $completed   = $connectTask.Wait(300)   # ms

        if ($completed -and $tcpClient.Connected) {
            return $false   # Port OCCUPÉ — quelque chose écoute
        }
        return $true        # Port LIBRE
    }
    catch {
        # Exception lors de la connexion = port refusé = LIBRE
        return $true
    }
    finally {
        if ($null -ne $tcpClient) {
            $tcpClient.Close()
            $tcpClient.Dispose()
        }
    }
}

# ══════════════════════════════════════════════════════════════════════════════
#  Fonction : Trouver la commande Docker Compose disponible
# ══════════════════════════════════════════════════════════════════════════════

function Get-ComposeCommand {
    <#
    .SYNOPSIS
        Retourne "docker compose" (v2 plugin) ou "docker-compose" (v1).
        Lève une exception si aucun n'est disponible.
    #>

    # Test Docker Compose v2 (plugin intégré à Docker Desktop)
    try {
        $null = & docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            return 'v2'
        }
    }
    catch { }

    # Fallback Docker Compose v1 (executable standalone)
    try {
        $null = & docker-compose --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Warn "Docker Compose v1 détecté. La v2 (incluse dans Docker Desktop) est recommandée."
            return 'v1'
        }
    }
    catch { }

    throw "Docker Compose introuvable. Installez Docker Desktop : https://docs.docker.com/desktop/windows/"
}

# ══════════════════════════════════════════════════════════════════════════════
#  Fonction : Exécuter Docker Compose avec les bons paramètres
# ══════════════════════════════════════════════════════════════════════════════

function Invoke-Compose {
    param(
        [string]   $ComposeVersion,
        [string[]] $Arguments
    )
    if ($ComposeVersion -eq 'v2') {
        & docker compose @Arguments
    }
    else {
        & docker-compose @Arguments
    }
}

# ══════════════════════════════════════════════════════════════════════════════
#  DÉBUT DU SCRIPT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

Write-Banner

# ── Étape 1 : Pré-requis ──────────────────────────────────────────────────────
Write-Step "Verification des pre-requis"

# Vérifier Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker n'est pas installé ou pas dans le PATH."
    Write-Host "  -> Installez Docker Desktop : https://docs.docker.com/desktop/windows/" -ForegroundColor Yellow
    exit 1
}

# Vérifier que le daemon Docker tourne
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw "daemon non disponible" }
}
catch {
    Write-Err "Le daemon Docker ne repond pas."
    Write-Host "  -> Lancez Docker Desktop depuis le menu Demarrer." -ForegroundColor Yellow
    exit 1
}

$dockerVersion = (docker --version) -replace 'Docker version ([^,]+).*','$1'
Write-Success "Docker trouve : v$dockerVersion"

# Vérifier Docker Compose
try {
    $composeVersion = Get-ComposeCommand
}
catch {
    Write-Err $_.Exception.Message
    exit 1
}

$composeVerStr = if ($composeVersion -eq 'v2') {
    (docker compose version --short 2>$null) -replace '\s',''
} else {
    ((docker-compose --version 2>$null) -replace '.*version ([^,]+).*','$1').Trim()
}
Write-Success "Docker Compose $composeVersion trouve : v$composeVerStr"

# ── Action --stop ──────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Step "Arret des containers AssurCore"
    Invoke-Compose -ComposeVersion $composeVersion -Arguments @('-p', $PROJECT_NAME, 'down')
    Write-Success "Containers arretes proprement."
    exit 0
}

# ── Action --reset ─────────────────────────────────────────────────────────────
if ($Reset) {
    Write-Step "Reset complet (containers + volumes)"
    Write-Warn "ATTENTION : Cette operation supprime toutes les donnees PostgreSQL !"
    $confirm = Read-Host "Confirmer ? Tapez 'oui' pour continuer"
    if ($confirm -ne 'oui') {
        Write-Info "Operation annulee."
        exit 0
    }
    Invoke-Compose -ComposeVersion $composeVersion -Arguments @('-p', $PROJECT_NAME, 'down', '-v', '--remove-orphans')
    if (Test-Path $DATA_DIR) {
        Remove-Item -Recurse -Force $DATA_DIR
        Write-Info "Dossier $DATA_DIR supprime."
    }
    Write-Success "Reset effectue. Relancez .\deploy_local.ps1 pour repartir de zero."
    exit 0
}

# ── Étape 2 : Création des dossiers ────────────────────────────────────────────
Write-Step "Creation de la structure de dossiers"

foreach ($dir in @($ADDONS_DIR, $DATA_DIR, $CONFIG_DIR)) {
    $fullPath = Join-Path $SCRIPT_DIR $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Info "Dossier cree : $fullPath"
    }
    else {
        Write-Info "Dossier existant : $fullPath"
    }
}

# ── Étape 3 : Synchronisation du module assurcore ──────────────────────────────
Write-Step "Synchronisation du module AssurCore"

$moduleSrc    = Join-Path $SCRIPT_DIR $MODULE_SRC
$moduleTarget = Join-Path $SCRIPT_DIR "$ADDONS_DIR\$MODULE_SRC"

if (Test-Path $moduleSrc) {
    if (-not (Test-Path $moduleTarget)) {
        Copy-Item -Path $moduleSrc -Destination $moduleTarget -Recurse -Force
        Write-Success "Module copie -> $moduleTarget"
    }
    else {
        # Mise à jour : copie par fichier modifié
        $srcItems = Get-ChildItem -Path $moduleSrc -Recurse -File
        $updated  = 0
        foreach ($srcFile in $srcItems) {
            $relPath = $srcFile.FullName.Substring($moduleSrc.Length)
            $dstFile = Join-Path $moduleTarget $relPath
            $dstDir  = Split-Path $dstFile -Parent
            if (-not (Test-Path $dstDir)) {
                New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            }
            if (-not (Test-Path $dstFile) -or
                $srcFile.LastWriteTime -gt (Get-Item $dstFile).LastWriteTime) {
                Copy-Item -Path $srcFile.FullName -Destination $dstFile -Force
                $updated++
            }
        }
        if ($updated -gt 0) {
            Write-Success "Module mis a jour ($updated fichier(s) modifie(s)) -> $moduleTarget"
        }
        else {
            Write-Info "Module a jour (aucune modification detectee)."
        }
    }
}
elseif (Test-Path $moduleTarget) {
    Write-Info "Module deja dans addons\ (dossier source absent - mode production normal)."
}
else {
    Write-Warn "Dossier '$MODULE_SRC\' introuvable dans $SCRIPT_DIR."
    Write-Warn "Copiez manuellement votre module dans $ADDONS_DIR\assurcore\"
}

# ── Étape 4 : Fichier de configuration odoo.conf ──────────────────────────────
Write-Step "Configuration Odoo"

$odooConf = Join-Path $SCRIPT_DIR "$CONFIG_DIR\odoo.conf"
if (-not (Test-Path $odooConf)) {
    Write-Info "Generation de $odooConf ..."
    @"
[options]
; -- Connexion base de donnees -----------------------------------------------
db_host     = db
db_port     = 5432
db_user     = odoo
db_password = odoo
db_name     = False

; -- Modules -----------------------------------------------------------------
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons

; -- Serveur HTTP -------------------------------------------------------------
xmlrpc_interface = 0.0.0.0
xmlrpc_port      = 8069
longpolling_port = 8072

; -- Performance (developpement local) ----------------------------------------
workers = 0

; -- Logs ---------------------------------------------------------------------
log_level   = info
log_handler = :INFO
logfile     = False

; -- Securite (DECOMMENTER ET CHANGER EN PRODUCTION) --------------------------
; admin_passwd = CHANGER_CE_MOT_DE_PASSE_FORT
; list_db = False
"@ | Set-Content -Path $odooConf -Encoding UTF8
    Write-Success "odoo.conf genere."
}
else {
    Write-Info "$odooConf deja present - conserve."
}

# ── Étape 5 : Détection du port libre ─────────────────────────────────────────
Write-Step "Recherche d'un port disponible ($PortStart -> $PORT_END)"

$availablePort = $null

for ($port = $PortStart; $port -le $PORT_END; $port++) {
    if (Test-PortFree -Port $port) {
        $availablePort = $port
        break
    }
    else {
        Write-Info "Port $port occupe -> essai suivant ..."
    }
}

if ($null -eq $availablePort) {
    Write-Err "Aucun port libre entre $PortStart et $PORT_END."
    Write-Host "  -> Liberez un port ou relancez avec : .\deploy_local.ps1 -PortStart 8080" -ForegroundColor Yellow
    exit 1
}

if ($availablePort -eq $PortStart) {
    Write-Success "Port $availablePort disponible."
}
else {
    Write-Success "Port $availablePort disponible (port $PortStart occupe)."
}

# Exporter la variable d'environnement pour docker-compose.yml
$env:ODOO_PORT = "$availablePort"
Write-Info "Variable exportee : ODOO_PORT=$($env:ODOO_PORT)"

# ── Étape 6 : Vérification docker-compose.yml ─────────────────────────────────
Write-Step "Validation de $COMPOSE_FILE"

if (-not (Test-Path (Join-Path $SCRIPT_DIR $COMPOSE_FILE))) {
    Write-Err "Fichier $COMPOSE_FILE introuvable dans $SCRIPT_DIR."
    exit 1
}
Write-Success "$COMPOSE_FILE trouve."

# ── Étape 7 : Lancement des containers ────────────────────────────────────────
Write-Step "Lancement des containers (arriere-plan)"

Write-Info "Verification des images Docker (pull si necessaire) ..."
try {
    Invoke-Compose -ComposeVersion $composeVersion `
                   -Arguments @('-p', $PROJECT_NAME, 'pull', '--quiet')
}
catch {
    Write-Warn "Pull ignore (mode offline ou images deja presentes)."
}

Write-Info "Demarrage des containers ..."
Invoke-Compose -ComposeVersion $composeVersion `
               -Arguments @('-p', $PROJECT_NAME, 'up', '-d', '--remove-orphans')

if ($LASTEXITCODE -ne 0) {
    Write-Err "Echec du lancement des containers (code $LASTEXITCODE)."
    Write-Host "  -> Consultez les logs : docker compose -p $PROJECT_NAME logs" -ForegroundColor Yellow
    exit 1
}

# Afficher le statut
Write-Host ""
Invoke-Compose -ComposeVersion $composeVersion -Arguments @('-p', $PROJECT_NAME, 'ps')

# ── Étape 8 : Health check Odoo ────────────────────────────────────────────────
Write-Step "Verification du demarrage Odoo (timeout : ${HEALTH_TIMEOUT}s)"

$elapsed      = 0
$sleepSecs    = 10
$odooReady    = $false

# Deux URLs à tester : /web/health (léger) puis /web (page principale)
# Pendant l'initialisation de la base (3-8 min sur Windows), /web/health
# retourne 500. On attend qu'il retourne 200 OU que /web réponde.
$healthUrl = "http://localhost:$availablePort/web/health"
$webUrl    = "http://localhost:$availablePort/web"

Write-Host ""
Write-Info "Odoo initialise la base 'assurcore_db' au premier demarrage."
Write-Info "Cette operation prend 3 a 8 minutes sur Docker Desktop Windows."
Write-Info "C'est NORMAL de voir des erreurs dans les logs pendant ce temps."
Write-Host ""
Write-Host "  Attente sur $healthUrl" -ForegroundColor DarkGray
Write-Host "  [" -NoNewline -ForegroundColor DarkGray

while ($elapsed -lt $HEALTH_TIMEOUT) {
    $httpCode = 0
    try {
        $response = Invoke-WebRequest -Uri $healthUrl `
                                      -TimeoutSec 5 `
                                      -UseBasicParsing `
                                      -ErrorAction SilentlyContinue
        $httpCode = $response.StatusCode
    }
    catch { }

    if ($httpCode -eq 200) {
        $odooReady = $true
        break
    }

    # Afficher le temps écoulé toutes les 60 secondes
    if ($elapsed -gt 0 -and $elapsed % 60 -eq 0) {
        Write-Host ""
        Write-Host ("  {0:D3}s — initialisation en cours (code HTTP: {1})..." -f $elapsed, $httpCode) `
                   -ForegroundColor DarkGray
        Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    } else {
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }

    Start-Sleep -Seconds $sleepSecs
    $elapsed += $sleepSecs
}

Write-Host "]" -ForegroundColor DarkGray
Write-Host ""

if ($odooReady) {
    Write-Success "Odoo pret ! Initialisation terminee en ${elapsed}s."
}
else {
    Write-Warn "Timeout atteint (${HEALTH_TIMEOUT}s). Odoo initialise peut-etre encore."
    Write-Host ""
    Write-Host "  -> Verifiez l'avancement :" -ForegroundColor Yellow
    Write-Host "     docker compose -p $PROJECT_NAME logs --tail=30 web" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  -> Quand vous voyez cette ligne dans les logs, Odoo est pret :" -ForegroundColor Yellow
    Write-Host "     'odoo.modules.loading: Modules loaded.' " -ForegroundColor Green
    Write-Host ""
    Write-Host "  -> Testez l'acces : http://localhost:$availablePort/web" -ForegroundColor Cyan
}

# ── Message de succès final ────────────────────────────────────────────────────
Write-SuccessBanner -Port $availablePort

Write-Host "Commandes utiles :" -ForegroundColor White
Write-Host "Commandes utiles :" -ForegroundColor White
Write-Host "  Logs en temps reel    : " -NoNewline; Write-Host "docker compose -p $PROJECT_NAME logs -f web" -ForegroundColor Cyan
Write-Host "  Arreter proprement    : " -NoNewline; Write-Host ".\deploy_local.ps1 -Stop" -ForegroundColor Cyan
Write-Host "  Redemarrer de zero    : " -NoNewline; Write-Host ".\deploy_local.ps1 -Reset" -ForegroundColor Cyan
Write-Host "  Statut des containers : " -NoNewline; Write-Host "docker compose -p $PROJECT_NAME ps" -ForegroundColor Cyan
Write-Host "  Module assurcore      : " -NoNewline; Write-Host "Installer depuis Odoo -> Apps -> Rechercher 'assurcore'" -ForegroundColor Cyan
Write-Host ""
Write-Host "Import ETL (apres creation de la base Odoo) :" -ForegroundColor White
Write-Host "  cd migration_scripts" -ForegroundColor Cyan
Write-Host "  python import_assurcore.py --dry-run" -ForegroundColor Cyan
Write-Host "  python import_assurcore.py" -ForegroundColor Cyan
Write-Host ""

# Affichage des logs si -Logs
if ($Logs) {
    Write-Info "Affichage des logs Odoo (Ctrl+C pour quitter) ..."
    Start-Sleep -Seconds 2
    Invoke-Compose -ComposeVersion $composeVersion `
                   -Arguments @('-p', $PROJECT_NAME, 'logs', '-f', 'web')
}
