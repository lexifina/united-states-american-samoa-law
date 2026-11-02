$log = Join-Path $env:LOCALAPPDATA 'gitlaw-cpu.log'
Add-Type -AssemblyName Microsoft.VisualBasic
$ci = New-Object Microsoft.VisualBasic.Devices.ComputerInfo
$hist = New-Object System.Collections.Generic.List[double]
while ($true) {
  $v = ((Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 5 -MaxSamples 12).CounterSamples | Measure-Object CookedValue -Average).Average
  $hist.Add($v); if ($hist.Count -gt 5) { $hist.RemoveAt(0) }
  # No WMI here: GlobalMemoryStatusEx via ComputerInfo is free; WMI queries cost wmiprvse CPU.
  $ram = 100 * (1 - $ci.AvailablePhysicalMemory / $ci.TotalPhysicalMemory)
  $line = '{0} cpu1={1:N0} cpu5={2:N0} ram={3:N0}' -f (Get-Date).ToUniversalTime().ToString('HH:mm'), $v, ($hist | Measure-Object -Average).Average, $ram
  Add-Content -Path $log -Value $line -Encoding utf8
  if ((Get-Item $log).Length -gt 200KB) { Get-Content $log -Tail 500 | Set-Content $log -Encoding utf8 }
}
