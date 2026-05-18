$WinSCP = "C:\Program Files (x86)\WinSCP\WinSCP.com"
$SessionUrl = "sftp://root:Btc*19%2175mB*20%2104KNEE@vps784643.ovh.net/"

Write-Host "Syncing and running update_ranks.sh on VPS..." -ForegroundColor Yellow

# Upload update_ranks.sh
& $WinSCP /ini=nul /command `
    "open `"$SessionUrl`" -hostkey=`"*`"" `
    "put `"d:\Robot\ASSURPROD\update_ranks.sh`" `"/root/assurcore_prod/update_ranks.sh`"" `
    "call cd /root/assurcore_prod && chmod +x update_ranks.sh && ./update_ranks.sh" `
    "exit"

Write-Host "Ranks and client states updated successfully on remote VPS." -ForegroundColor Green
