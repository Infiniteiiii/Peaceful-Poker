[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "Peaceful Poker Windows builds must run on Windows."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpectedVenv = (Resolve-Path (Join-Path $Root ".venv") -ErrorAction Stop).Path
$ExpectedPython = (Resolve-Path (Join-Path $ExpectedVenv "Scripts\python.exe") -ErrorAction Stop).Path
$ActiveVenv = if ($env:VIRTUAL_ENV) {
    [System.IO.Path]::GetFullPath($env:VIRTUAL_ENV).TrimEnd('\')
} else {
    ""
}
$ActivePython = (Get-Command python -ErrorAction Stop).Source

if ($ActiveVenv -ne $ExpectedVenv.TrimEnd('\') -or $ActivePython -ne $ExpectedPython) {
    throw "Activate the repository virtual environment first: .\.venv\Scripts\Activate.ps1"
}

$Python = $ExpectedPython
$Spec = Join-Path $Root "Peaceful Poker.spec"
$BuildPath = Join-Path $Root "build"
$DistPath = Join-Path $Root "dist"
$ApplicationPath = Join-Path $DistPath "Peaceful Poker"
$ExpectedExe = Join-Path $ApplicationPath "Peaceful Poker.exe"
$SmokeScript = Join-Path $PSScriptRoot "smoke_windows_package.ps1"

function Invoke-Python {
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $args"
    }
}

function Remove-ReleaseDirectory([string] $Path, [string] $ExpectedLeaf) {
    $FullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $RootPrefix = $Root.TrimEnd('\') + '\'
    if (-not $FullPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $FullPath"
    }
    if ([System.IO.Path]::GetFileName($FullPath) -ne $ExpectedLeaf) {
        throw "Refusing to remove unexpected release directory: $FullPath"
    }
    if (Test-Path -LiteralPath $FullPath) {
        Remove-Item -Recurse -Force -LiteralPath $FullPath
    }
}

Push-Location $Root
try {
    Write-Host "Using virtual environment: $ExpectedVenv"
    Invoke-Python -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ is required'; print(sys.version)"
    Invoke-Python -c "import PyInstaller, PySide6, mypy, pytest, pytestqt, ruff; print('Required build packages are installed.')"
    Invoke-Python -c "import tomllib; from pathlib import Path; from poker_trainer import __version__; version = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']; metadata = Path('packaging/windows_version_info.txt').read_text(encoding='utf-8'); assert version == __version__; assert metadata.count(version) >= 2; print(f'Release version: {version}')"

    $env:PYTHONFAULTHANDLER = "1"
    Invoke-Python -m pytest -p no:cacheprovider
    Invoke-Python -m ruff format --check .
    Invoke-Python -m ruff check .
    Invoke-Python -m mypy src
    Invoke-Python -m pip check

    Remove-ReleaseDirectory $BuildPath "build"
    Remove-ReleaseDirectory $DistPath "dist"

    Invoke-Python -m PyInstaller --clean --noconfirm $Spec
    if (-not (Test-Path -LiteralPath $ExpectedExe -PathType Leaf)) {
        throw "Expected executable was not created: $ExpectedExe"
    }

    $PlatformPlugins = @(Get-ChildItem -LiteralPath $ApplicationPath -Recurse -Filter "qwindows.dll")
    if ($PlatformPlugins.Count -ne 1) {
        throw "Expected exactly one bundled qwindows.dll; found $($PlatformPlugins.Count)."
    }
    Write-Host "Qt platform plugin: $($PlatformPlugins[0].FullName)"

    & $SmokeScript -ApplicationDirectory $ApplicationPath
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged smoke verification failed with exit code $LASTEXITCODE."
    }

    Write-Host "Windows application build passed all checks."
    Write-Host "Output: $ExpectedExe"
}
finally {
    Pop-Location
}
