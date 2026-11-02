# Parses, verifies and publishes each Spanish unit's repealed norms as soon as the one fetch process has finished that
# unit (its "fetched" line in logs/derog-fetch.out), one unit at a time, BelowNormal, waiting while cpu5 > 92 or ram > 85.
param([string]$Day = '2026-10-31')
Set-Location C:\Users\alany\Documents\lexifina\scripts
$units = 'cantabria','castile-la-mancha','murcia','asturias','extremadura','la-rioja','canary-islands','galicia','andalusia','madrid','navarre','aragon','balearic-islands','basque-country','valencia','catalonia'
$log = 'world-law/logs/derog-drive.log'
function Run($argv) {
  while ($true) {
    $l = (Get-Content "$env:LOCALAPPDATA\gitlaw-cpu.log" -Tail 1)
    if ($l -match 'cpu5=(\d+).*ram=(\d+)' -and ([int]$matches[1] -gt 92 -or [int]$matches[2] -gt 85)) { Start-Sleep 60 } else { break }
  }
  $p = Start-Process -FilePath python -ArgumentList (@('-X','utf8','world-law/es_ccaa_derog.py') + $argv) -RedirectStandardOutput world-law/logs/derog-step.out -RedirectStandardError world-law/logs/derog-step.err -NoNewWindow -PassThru
  $p.PriorityClass = 'BelowNormal'; $p.WaitForExit()
  ((Get-Content world-law/logs/derog-step.out) + (Get-Content world-law/logs/derog-step.err | Select-Object -Last 3)) -join ' | '
}
foreach ($u in $units) {
  while (-not (Select-String -Path world-law/logs/derog-fetch.out -Pattern "^\S+ ${u}: " -Quiet)) {
    if (Select-String -Path world-law/logs/derog-fetch.out -Pattern 'STOPPED' -Quiet) { Add-Content $log "$((Get-Date).ToUniversalTime().ToString('s'))Z fetch stopped before $u"; exit 2 }
    Start-Sleep 20
  }
  $r1 = Run @('parse', $u, $Day)
  Add-Content $log "$((Get-Date).ToUniversalTime().ToString('s'))Z $u parse: $r1"
  $r2 = Run @('publish', $u, $Day)
  Add-Content $log "$((Get-Date).ToUniversalTime().ToString('s'))Z $u publish: $r2"
}
Add-Content $log "$((Get-Date).ToUniversalTime().ToString('s'))Z all units done"
