# Remove the Firefly scrape watchdog scheduled task. The watchdog also removes itself once every
# candidate has been read, so this is only needed to cancel a run early.
param([string]$TaskName = "FireflyScrapeWatchdog")
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
schtasks /delete /tn $TaskName /f *> $null
Write-Output "Watchdog '$TaskName' removed."
