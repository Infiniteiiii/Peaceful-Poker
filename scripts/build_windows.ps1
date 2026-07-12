[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$ExpectedExe = Join-Path $Root "dist\Peaceful Poker\Peaceful Poker.exe"

function Invoke-Python {
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $args"
    }
}

Push-Location $Root
try {
    Invoke-Python -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ is required'"
    Invoke-Python -m pip install -e ".[dev,build]"
    Invoke-Python -m pip check
    Invoke-Python -m pytest -p no:cacheprovider
    Invoke-Python -m ruff format --check .
    Invoke-Python -m ruff check .
    Invoke-Python -m mypy src

    $BuildPath = Join-Path $Root "build"
    $DistPath = Join-Path $Root "dist"
    if (Test-Path -LiteralPath $BuildPath) { Remove-Item -Recurse -Force -LiteralPath $BuildPath }
    if (Test-Path -LiteralPath $DistPath) { Remove-Item -Recurse -Force -LiteralPath $DistPath }

    Invoke-Python -m PyInstaller --noconfirm "Peaceful Poker.spec"
    if (-not (Test-Path -LiteralPath $ExpectedExe)) {
        throw "Expected executable was not created: $ExpectedExe"
    }
    Write-Host "Built: $ExpectedExe"
}
finally {
    Pop-Location
}
