$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Fetching Odoo container logs from VPS..." -ForegroundColor Yellow

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "call cd /root/assurcore_prod && docker-compose logs --tail=100 web" `
    "exit"

Write-Host "Logs fetched." -ForegroundColor Green
