$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Syncing and running update_company.sh on VPS..." -ForegroundColor Yellow

# Upload update_company.sh
& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "put `"d:\Robot\ASSURPROD\update_company.sh`" `"/root/assurcore_prod/update_company.sh`"" `
    "call cd /root/assurcore_prod && chmod +x update_company.sh && ./update_company.sh" `
    "exit"

Write-Host "Update company script executed successfully." -ForegroundColor Green
