[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The Peaceful Poker installer must be built on Windows."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApplicationPath = Join-Path $Root "dist\Peaceful Poker"
$Exe = Join-Path $ApplicationPath "Peaceful Poker.exe"
$Iss = Join-Path $Root "installer\PeacefulPoker.iss"
$Icon = Join-Path $Root "src\poker_trainer\resources\peaceful_poker.ico"
$OutputDir = Join-Path $Root "dist\installer"
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw "A successful one-folder build is required first: $Exe"
}
if (@(Get-ChildItem -LiteralPath $ApplicationPath -Recurse -Filter "qwindows.dll").Count -ne 1) {
    throw "The application folder does not contain exactly one qwindows.dll. Rebuild it first."
}

$VersionLine = Select-String -LiteralPath (Join-Path $Root "pyproject.toml") -Pattern '^version = "([^"]+)"$'
if ($VersionLine.Matches.Count -ne 1) {
    throw "Could not read one release version from pyproject.toml."
}
$Version = $VersionLine.Matches[0].Groups[1].Value

$IsccCommand = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$Candidates = @(
    $(if ($IsccCommand) { $IsccCommand.Source }),
    $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe" }),
    $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe" })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$Candidates = @($Candidates)
if ($Candidates.Count -eq 0) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php, then rerun this script."
}
$Iscc = $Candidates[0]
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$InstallerPath = Join-Path $OutputDir "Peaceful-Poker-Setup-$Version.exe"
if (Test-Path -LiteralPath $InstallerPath) {
    Remove-Item -Force -LiteralPath $InstallerPath
}

& $Iscc "/DMyAppVersion=$Version" "/DMySourceDir=$ApplicationPath" "/DMyOutputDir=$OutputDir" "/DMyIconFile=$Icon" $Iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
    throw "Expected installer was not created: $InstallerPath"
}

$Installer = Get-Item -LiteralPath $InstallerPath
$Checksum = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash
Write-Host "Installer: $($Installer.FullName)"
Write-Host ("Size: {0:N0} bytes ({1:N2} MiB)" -f $Installer.Length, ($Installer.Length / 1MB))
Write-Host "SHA-256: $Checksum"
