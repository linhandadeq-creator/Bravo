# Stops the Bravo backend/frontend started by the launcher (PIDs recorded in
# %LOCALAPPDATA%\Bravo\pids.json).
$ErrorActionPreference = "SilentlyContinue"
$pidsFile = Join-Path $env:LOCALAPPDATA "Bravo\pids.json"
if (Test-Path $pidsFile) {
    $ids = Get-Content $pidsFile -Raw | ConvertFrom-Json
    foreach ($id in $ids) {
        Stop-Process -Id $id -Force
    }
    Remove-Item $pidsFile -Force
    Write-Host "Bravo stopped."
} else {
    Write-Host "Bravo is not running (no pid file)."
}
