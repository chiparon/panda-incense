$ErrorActionPreference = 'Stop'
$pythonPath = (Get-Command python).Source
$pythonwPath = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { $pythonwPath = $pythonPath }
$statusFile = Join-Path $PSScriptRoot 'runtime-status.json'
if (Test-Path -LiteralPath $statusFile) {
    $petState = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
    $petProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($petState.pid)" -ErrorAction SilentlyContinue
    if ($petProcess -and $petProcess.CommandLine -and $petProcess.CommandLine.Contains((Join-Path $PSScriptRoot 'deskpet.py'))) { Write-Output 'Panda Incense is already running.'; exit }
}
Start-Process -FilePath $pythonwPath -ArgumentList ('"' + (Join-Path $PSScriptRoot 'deskpet.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
