[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$Exe = Join-Path $Root "dist\Peaceful Poker\Peaceful Poker.exe"
$SmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) "PeacefulPokerReleaseSmoke"
$Report = Join-Path $SmokeRoot "packaged-smoke.json"

function Invoke-Python {
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $args"
    }
}

Push-Location $Root
try {
    Invoke-Python -m pip check
    Invoke-Python -m pytest -p no:cacheprovider
    Invoke-Python -m ruff format --check .
    Invoke-Python -m ruff check .
    Invoke-Python -m mypy src
    if (-not (Test-Path -LiteralPath $Exe)) { throw "Missing executable: $Exe" }

    if (Test-Path -LiteralPath $SmokeRoot) {
        Remove-Item -Recurse -Force -LiteralPath $SmokeRoot
    }
    New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null
    $env:LOCALAPPDATA = Join-Path $SmokeRoot "LocalAppData"
    $env:PEACEFUL_POKER_SMOKE_REPORT = $Report
    Remove-Item Env:PEACEFUL_POKER_AUTOCLOSE_MS -ErrorAction SilentlyContinue

    $Process = Start-Process -FilePath $Exe -WorkingDirectory $SmokeRoot -PassThru
    if (-not $Process.WaitForExit(90000)) {
        $Process.Kill()
        throw "Packaged application did not finish its smoke analysis within 90 seconds."
    }
    if ($Process.ExitCode -ne 0) { throw "Packaged application exited with $($Process.ExitCode)." }
    if (-not (Test-Path -LiteralPath $Report)) { throw "Packaged smoke report was not created." }

    $Smoke = Get-Content -Raw -LiteralPath $Report | ConvertFrom-Json
    if (-not $Smoke.analysis_complete) { throw "Packaged analysis did not complete." }
    if (-not $Smoke.action_aware_complete) { throw "Packaged action-aware analysis did not complete." }
    if (-not $Smoke.resources_loaded) { throw "Packaged resources did not load." }
    if (-not (Test-Path -LiteralPath $Smoke.saved_hand)) { throw "Packaged save was not created." }
    if ($Smoke.user_data_dir.StartsWith((Join-Path $Root "dist"))) {
        throw "User data was incorrectly written inside the application bundle."
    }
    Write-Host "Packaged verification passed: $Report"
}
finally {
    Pop-Location
}
