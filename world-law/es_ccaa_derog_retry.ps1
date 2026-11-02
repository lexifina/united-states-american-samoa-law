# After the driver (PID given) exits: publish every Spanish unit whose derogadas part has no PUBLISH yet, one at a time,
# BelowNormal, waiting while cpu5 > 92 or ram > 85. Results go to each unit's PROGRESS.md and logs/derog-retry.log.
param([int]$Wait = 0, [string]$Day = '2026-10-31')
Set-Location C:\Users\alany\Documents\lexifina\scripts
if ($Wait) { while (Get-Process -Id $Wait -ErrorAction SilentlyContinue) { Start-Sleep 20 } }
foreach ($d in Get-ChildItem -Directory spain-*-law) {
  $u = $d.Name -replace '^spain-','' -replace '-law$',''
  $parts = Get-ChildItem "$($d.FullName)\corpus.d\6*-derogadas-*.json" -ErrorAction SilentlyContinue
  if (-not $parts) { continue }
  if (-not ($parts | Where-Object { -not (Test-Path ($_.FullName -replace '\.json$','.PUBLISH')) })) { continue }
  while ($true) {
    $l = (Get-Content "$env:LOCALAPPDATA\gitlaw-cpu.log" -Tail 1)
    if ($l -match 'cpu5=(\d+).*ram=(\d+)' -and ([int]$matches[1] -gt 92 -or [int]$matches[2] -gt 85)) { Start-Sleep 60 } else { break }
  }
  $p = Start-Process -FilePath python -ArgumentList '-X','utf8','world-law/es_ccaa_derog.py','publish',$u,$Day -RedirectStandardOutput "world-law/logs/derog-retry-$u.out" -RedirectStandardError "world-law/logs/derog-retry-$u.err" -NoNewWindow -PassThru
  $p.PriorityClass = 'BelowNormal'; $p.WaitForExit()
  $s = "$((Get-Date).ToUniversalTime().ToString('s'))Z $u : $((Get-Content "world-law/logs/derog-retry-$u.out") -join ' ')"
  if ($s.Length -gt 400) { $s = $s.Substring(0, 400) }
  $s | Out-File -Append -Encoding utf8 world-law/logs/derog-retry.log
}
"$((Get-Date).ToUniversalTime().ToString('s'))Z retry done" | Out-File -Append -Encoding utf8 world-law/logs/derog-retry.log
