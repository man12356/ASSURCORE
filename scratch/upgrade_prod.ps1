$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Syncing and running upgrade_prod.sh on VPS..." -ForegroundColor Yellow

# Upload upgrade_prod.sh
& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "put `"d:\Robot\ASSURPROD\upgrade_prod.sh`" `"/root/assurcore_prod/upgrade_prod.sh`"" `
    "call cd /root/assurcore_prod && chmod +x upgrade_prod.sh && ./upgrade_prod.sh" `
    "exit"

Write-Host "Module upgrade script executed successfully." -ForegroundColor Green
