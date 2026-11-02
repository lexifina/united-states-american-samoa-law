# Stops the orchestrator loops cleanly: each loop finishes its current pass and exits.
#   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\stop.ps1"
$H = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType File -Force "$H\stop-repoint", "$H\stop-pushwatch" | Out-Null
# The CPU logger has no pass to finish; stop exactly the PID it was started with.
if (Test-Path "$H\cpulog.pid") {
    $id = [int](Get-Content "$H\cpulog.pid")
    Stop-Process -Id $id -Force -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item "$H\cpulog.pid"
}
'stop requested: repoint and pushwatch exit after their current pass (up to ~10 min); cpulog stopped'
