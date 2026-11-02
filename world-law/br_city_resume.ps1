# Private (never published). gitlaw-scraper-dell 2026-11-01. One command to (re)start the Brazilian city builds after a
# sleep, a reboot or a killed shell:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\alany\Documents\lexifina\scripts\world-law\br_city_resume.ps1
#
# Idempotent. For each city: starts its fetch from cache (one process, one request at a time, >= 3 s apart, BelowNormal)
# unless the list is done, the fetch is already running, or the host has a STOP file (never removed here: check the host
# by hand first and log it in SCRAPING-LOG.md); then starts its verify/publish loop (br_city_<key>.sh loop ->
# br_city_loop.sh, BelowNormal) unless it is already running. PIDs: <folder>\fetch.pid, <folder>\loop.pid, my-pids.txt.
$S = 'C:\Users\alany\Documents\lexifina\scripts'
$W = "$S\world-law"
$bash = 'C:\Program Files\Git\usr\bin\bash.exe'
$cities = @(
  @{ key = 'sp'; dir = 'brazil-sao-paulo-city-law'; stop = '.cache\STOP'; fetch = @('-X', 'utf8', '-u', 'fetch.py', '--years', '2024-1892') },
  @{ key = 'mc'; dir = 'brazil-maceio-city-law'; stop = '.cache\www\STOP'; fetch = @('-X', 'utf8', '-u', 'fetch.py', '--pdfs') }
)
function Alive($pidFile, $pattern) {
  if (-not (Test-Path $pidFile)) { return $false }
  $id = "$(Get-Content $pidFile -TotalCount 1)".Trim()
  if (-not $id) { return $false }
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
  return ($null -ne $p -and $p.CommandLine -match $pattern)
}
$now = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
foreach ($c in $cities) {
  $d = Join-Path $S $c.dir
  & $bash "$W/br_city_$($c.key).sh" done
  $listDone = ($LASTEXITCODE -eq 0)
  if ($listDone) { "$($c.dir): fetch list already done" }
  elseif (Alive "$d\fetch.pid" 'fetch\.py') { "$($c.dir): fetch already running (PID $(Get-Content $d\fetch.pid))" }
  elseif (Test-Path (Join-Path $d $c.stop)) { "$($c.dir): host STOP file present; fetch NOT started (check the host by hand)" }
  else {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmm')
    $p = Start-Process -FilePath python -ArgumentList $c.fetch -WorkingDirectory $d -RedirectStandardOutput "$d\fetch-$stamp.log" `
         -RedirectStandardError "$d\fetch-$stamp.err" -WindowStyle Hidden -PassThru
    $p.PriorityClass = 'BelowNormal'
    "$($p.Id)" | Out-File -Encoding ascii "$d\fetch.pid"
    "$($p.Id) python $($c.fetch -join ' ') started $now by br_city_resume.ps1 (log fetch-$stamp.log)" | Out-File -Append -Encoding utf8 "$d\my-pids.txt"
    "$($c.dir): fetch started, PID $($p.Id), log fetch-$stamp.log"
  }
  if (Alive "$d\loop.pid" 'br_city_') { "$($c.dir): loop already running (PID $(Get-Content $d\loop.pid))"; continue }
  $l = Start-Process -FilePath $bash -ArgumentList "$W/br_city_$($c.key).sh", 'loop' -WorkingDirectory $d -WindowStyle Hidden -PassThru
  $l.PriorityClass = 'BelowNormal'
  "$($l.Id)" | Out-File -Encoding ascii "$d\loop.pid"
  "$($l.Id) br_city_$($c.key).sh loop started $now by br_city_resume.ps1" | Out-File -Append -Encoding utf8 "$d\my-pids.txt"
  "$($c.dir): loop started, PID $($l.Id)"
}
