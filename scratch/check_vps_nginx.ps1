$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Checking Nginx configurations on remote VPS..." -ForegroundColor Yellow

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "call systemctl status nginx || true" `
    "call nginx -V || true" `
    "call ls -la /etc/nginx/sites-enabled/ || true" `
    "call cat /etc/nginx/sites-enabled/* || true" `
    "exit"
