$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Listing containers and port bindings on remote VPS..." -ForegroundColor Yellow

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "call docker ps -a" `
    "call ss -tulpn" `
    "exit"
