# Starts the global-law orchestrator loops outside any Claude session, so they keep running when a session closes.
# Safe to run again: a loop whose PID file points at a live process is left alone.
#   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\gitlaw-orchestrator\start.ps1"
#   ... start.ps1 -Only repoint,pushwatch    start just those loops
param([string[]]$Only)
$H = Split-Path -Parent $MyInvocation.MyCommand.Path
$bash = 'C:\Program Files\Git\bin\bash.exe'
$pythonw = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"

function Alive($pidFile, $match) {
    if (-not (Test-Path $pidFile)) { return $false }
    # bash PID files hold the MSYS pid; match on the command line instead, which is reliable on Windows
    $p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($match) }
    return [bool]$p
}

function Launch($cmd, $hidden) {
    # Win32_Process.Create starts the process outside the caller's process tree and job object.
    # Bash loops go through launch_hidden.py (pythonw), which gives the loop CREATE_NO_WINDOW: a hidden console its
    # git/python children inherit, so no window opens (memory note detached_no_console_windows, 2026-11-04).
    if ($hidden) {
        Remove-Item "$H\launch_hidden.last" -ErrorAction SilentlyContinue
        $cmd = "`"$pythonw`" `"$H\launch_hidden.py`" $cmd"
    }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd; CurrentDirectory = $H }
    if ($r.ReturnValue -ne 0) { throw "launch failed ($($r.ReturnValue)): $cmd" }
    $id = $r.ProcessId
    if ($hidden) {
        for ($i = 0; $i -lt 20 -and -not (Test-Path "$H\launch_hidden.last"); $i++) { Start-Sleep -Milliseconds 250 }
        if (Test-Path "$H\launch_hidden.last") { $id = [int](Get-Content "$H\launch_hidden.last") }
    } else {
        Start-Sleep -Milliseconds 500
    }
    # Normal, not BelowNormal: these loops are light, but at BelowNormal 28 busy workers starved them on 2026-11-04
    # (speedwatch and pointer passes ran into their deadlines; global-law pins stalled). Heavy children (describe.py)
    # still lower their own priority.
    try { (Get-Process -Id $id).PriorityClass = 'Normal' } catch {}
    return $id
}


$loops = @(
    @{ Name = 'repoint';   Match = 'repoint_loop.sh'; Pid = "$H\repoint.pid";   Cmd = "`"$bash`" `"$H\repoint_loop.sh`"" },
    @{ Name = 'pushwatch'; Match = 'pushwatch.sh';    Pid = "$H\pushwatch.pid"; Cmd = "`"$bash`" `"$H\pushwatch.sh`"" },
    @{ Name = 'speedwatch'; Match = 'speedwatch.sh'; Pid = "$H\speedwatch.pid"; Cmd = "`"$bash`" `"$H\speedwatch.sh`"" },
    @{ Name = 'goaltrack'; Match = 'goaltrack.sh'; Pid = "$H\goaltrack.pid"; Cmd = "`"$bash`" `"$H\goaltrack.sh`"" },
    @{ Name = 'cpulog';    Match = 'cpu_log.ps1';     Pid = "$H\cpulog.pid";    Cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$H\cpu_log.ps1`"" }
)
if ($Only) { $Only = $Only -split ',' | ForEach-Object { $_.Trim() }; $loops = $loops | Where-Object { $Only -contains $_.Name } }
foreach ($l in $loops) { Remove-Item "$H\stop-$($l.Name)" -ErrorAction SilentlyContinue }
foreach ($l in $loops) {
    if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($l.Match) }) {
        "$($l.Name): already running"
    } else {
        $id = Launch $l.Cmd ($l.Name -ne 'cpulog')
        if ($l.Name -eq 'cpulog') { Set-Content -Path $l.Pid -Value $id }
        "$($l.Name): started (pid $id)"
    }
}

# The pointer loop's heartbeat: when its last completed pass was, and what it did (pushwatch alerts after 30 min).
if (Test-Path "$H\heartbeat.json") {
    $hb = Get-Content "$H\heartbeat.json" -Raw | ConvertFrom-Json
    $age = [int]((Get-Date).ToUniversalTime() - [datetime]::Parse($hb.last_success_at).ToUniversalTime()).TotalMinutes
    "repoint heartbeat: last pass completed $age min ago ($($hb.last_success_at), $($hb.result))" + $(if ($age -gt 30) { ' -- STALLED' } else { '' })
}
