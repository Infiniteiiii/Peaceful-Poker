[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$ApplicationPath = Join-Path $Root "dist\Peaceful Poker"

function Invoke-Python {
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $args"
    }
}

Push-Location $Root
try {
    $env:PYTHONFAULTHANDLER = "1"
    Invoke-Python -m pytest -p no:cacheprovider
    Invoke-Python -m ruff format --check .
    Invoke-Python -m ruff check .
    Invoke-Python -m mypy src
    Invoke-Python -m pip check

    & (Join-Path $PSScriptRoot "smoke_windows_package.ps1") -ApplicationDirectory $ApplicationPath
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged smoke verification failed with exit code $LASTEXITCODE."
    }
    Write-Host "Source and packaged verification passed."
}
finally {
    Pop-Location
}
