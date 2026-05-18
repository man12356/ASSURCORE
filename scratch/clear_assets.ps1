$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Connecting to VPS and clearing Odoo asset cache in database..." -ForegroundColor Yellow

& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "put `"d:\Robot\ASSURPROD\rebuild_assets.sh`" `"/root/assurcore_prod/rebuild_assets.sh`"" `
    "call cd /root/assurcore_prod && chmod +x rebuild_assets.sh && ./rebuild_assets.sh" `
    "exit"

Write-Host "Asset cache cleared successfully." -ForegroundColor Green
