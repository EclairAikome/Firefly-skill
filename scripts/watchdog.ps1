# Firefly scrape watchdog (heartbeat). Run by a Task Scheduler job every ~5 minutes.
# Each tick: log a heartbeat with progress; if the detail-read stalled or died, relaunch a
# bounded pass on a FRESH session; when every candidate is read, write COMPLETE and delete the
# scheduled task (self-stop). Because Task Scheduler owns this, it survives the Claude session
# being torn down -- which is exactly when a plain background command would silently stop.
param(
  [Parameter(Mandatory=$true)][string]$SkillDir,
  [Parameter(Mandatory=$true)][string]$RunDir,
  [Parameter(Mandatory=$true)][string]$BrowserId,
  [int]$Chunk = 40,
  [string]$TaskName = "FireflyScrapeWatchdog",
  [switch]$NoLaunch   # testing: log the decision but do not actually start a read pass
)
$ErrorActionPreference = "SilentlyContinue"
$cand   = Join-Path $RunDir "candidates.json"
$detDir = Join-Path $RunDir "details"
$hb     = Join-Path $RunDir "heartbeat.log"
$ts     = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

if (-not (Test-Path $cand)) { Add-Content $hb "$ts ERROR: no candidates.json at $RunDir"; exit 1 }

# progress: unique candidate ids vs non-empty detail files
$ids = [regex]::Matches((Get-Content $cand -Raw), '"id":\s*"(\d+)"') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$total = @($ids).Count
$done  = @(Get-ChildItem $detDir -Filter *.json -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 50 }).Count

# is a read pass already running?
$running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'read_details' })

# completion -> mark done and remove the scheduled task (stop heartbeating)
if ($total -gt 0 -and $done -ge $total) {
  New-Item -ItemType File -Path (Join-Path $RunDir "COMPLETE") -Force | Out-Null
  Add-Content $hb "$ts COMPLETE done=$done/$total -> removing watchdog task '$TaskName'"
  schtasks /delete /tn $TaskName /f *> $null
  exit 0
}

if ($running.Count -gt 0) {
  Add-Content $hb "$ts OK done=$done/$total ; read pass alive (pid $($running.ProcessId -join ','))"
  exit 0
}

# stalled or never started -> relaunch a bounded pass on a fresh session (detached)
# Git Bash is usually NOT on PowerShell's PATH, so resolve bash.exe robustly: PATH, then derive
# from git.exe (git IS usually on PATH), then common install locations.
$bash = (Get-Command bash -ErrorAction SilentlyContinue).Source
if (-not $bash) {
  $git = (Get-Command git -ErrorAction SilentlyContinue).Source
  if ($git) { $c = Join-Path (Split-Path (Split-Path $git)) "bin\bash.exe"; if (Test-Path $c) { $bash = $c } }
}
if (-not $bash) { foreach ($p in @("C:\Program Files\Git\bin\bash.exe","C:\Program Files\Git\usr\bin\bash.exe","$env:LOCALAPPDATA\Programs\Git\bin\bash.exe")) { if (Test-Path $p) { $bash = $p; break } } }
$sess = "wd" + [int][double]::Parse((Get-Date -UFormat %s))
$rd   = ($SkillDir -replace '\\','/') + "/scripts/read_details.sh"
Add-Content $hb "$ts RESTART done=$done/$total ; no read pass running -> launching session=$sess chunk=$Chunk"
if ($NoLaunch) { Add-Content $hb "$ts (NoLaunch: skipped actual read pass)"; exit 0 }
if ($bash) {
  Start-Process -FilePath $bash -ArgumentList @($rd, $SkillDir, $RunDir, $sess, "$Chunk", $BrowserId) -WindowStyle Hidden
} else {
  Add-Content $hb "$ts ERROR: bash not found; cannot relaunch read pass"
}
exit 0
