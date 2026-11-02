# Starts the global-law orchestrator loops outside any Claude session, so they keep running when a session closes.
# Safe to run again: a loop whose PID file points at a live process is left alone.
#   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\start.ps1"
$H = Split-Path -Parent $MyInvocation.MyCommand.Path
$bash = 'C:\Program Files\Git\bin\bash.exe'

function Alive($pidFile, $match) {
    if (-not (Test-Path $pidFile)) { return $false }
    # bash PID files hold the MSYS pid; match on the command line instead, which is reliable on Windows
    $p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($match) }
    return [bool]$p
}

function Launch($cmd) {
    # Win32_Process.Create starts the process outside the caller's process tree and job object.
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $H }
    if ($r.ReturnValue -ne 0) { throw "launch failed ($($r.ReturnValue)): $cmd" }
    Start-Sleep -Milliseconds 500
    try { (Get-Process -Id $r.ProcessId).PriorityClass = 'BelowNormal' } catch {}
    return $r.ProcessId
}

Remove-Item "$H\stop-repoint", "$H\stop-pushwatch", "$H\stop-cpulog", "$H\stop-speedwatch", "$H\stop-goaltrack" -ErrorAction SilentlyContinue

$loops = @(
    @{ Name = 'repoint';   Match = 'repoint_loop.sh'; Pid = "$H\repoint.pid";   Cmd = "`"$bash`" `"$H\repoint_loop.sh`"" },
    @{ Name = 'pushwatch'; Match = 'pushwatch.sh';    Pid = "$H\pushwatch.pid"; Cmd = "`"$bash`" `"$H\pushwatch.sh`"" },
    @{ Name = 'speedwatch'; Match = 'speedwatch.sh'; Pid = "$H\speedwatch.pid"; Cmd = "`"$bash`" `"$H\speedwatch.sh`"" },
    @{ Name = 'goaltrack'; Match = 'goaltrack.sh'; Pid = "$H\goaltrack.pid"; Cmd = "`"$bash`" `"$H\goaltrack.sh`"" },
    @{ Name = 'cpulog';    Match = 'cpu_log.ps1';     Pid = "$H\cpulog.pid";    Cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$H\cpu_log.ps1`"" }
)
foreach ($l in $loops) {
    if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($l.Match) }) {
        "$($l.Name): already running"
    } else {
        $id = Launch $l.Cmd
        if ($l.Name -eq 'cpulog') { Set-Content -Path $l.Pid -Value $id }
        "$($l.Name): started (pid $id)"
    }
}
