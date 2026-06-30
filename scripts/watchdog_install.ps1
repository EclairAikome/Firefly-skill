# Install the Firefly scrape watchdog as a Windows Scheduled Task that runs every N minutes.
# The task is owned by Task Scheduler, so it keeps the long detail-read alive and auto-resuming
# even after the Claude session that started it is torn down.
#   Example:
#   powershell -ExecutionPolicy Bypass -File watchdog_install.ps1 `
#     -SkillDir "C:\Users\me\.claude\skills\Firefly-skill" `
#     -RunDir   "C:\Users\me\.claude\skills\Firefly-skill\state\run_2026-06-30" `
#     -BrowserId "chrome_local_104234741330346144"
param(
  [Parameter(Mandatory=$true)][string]$SkillDir,
  [Parameter(Mandatory=$true)][string]$RunDir,
  [Parameter(Mandatory=$true)][string]$BrowserId,
  [int]$IntervalMinutes = 5,
  [int]$Chunk = 40,
  [string]$TaskName = "FireflyScrapeWatchdog"
)
$wd = Join-Path $SkillDir "scripts\watchdog.ps1"
$ps = (Get-Command powershell).Source
$argString = "-NoProfile -ExecutionPolicy Bypass -File `"$wd`" -SkillDir `"$SkillDir`" -RunDir `"$RunDir`" -BrowserId `"$BrowserId`" -Chunk $Chunk -TaskName `"$TaskName`""

$action   = New-ScheduledTaskAction -Execute $ps -Argument $argString
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
              -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
              -RepetitionDuration (New-TimeSpan -Days 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName   # fire the first heartbeat now, do not wait the interval
Write-Output "Watchdog '$TaskName' installed: heartbeat every $IntervalMinutes min."
Write-Output "Progress log -> $RunDir\heartbeat.log ; remove with watchdog_remove.ps1 (auto-removes on completion)."
