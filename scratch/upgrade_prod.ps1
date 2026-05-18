$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Connecting to VPS and running direct Odoo upgrade..." -ForegroundColor Yellow

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "call cd /root/assurcore_prod && docker-compose exec -T web odoo -d assurcore_db -u assurcore --stop-after-init --http-port=8099" `
    "exit"

Write-Host "Odoo upgrade command completed." -ForegroundColor Green
