[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The portable Windows ZIP must be created on Windows."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistPath = Join-Path $Root "dist"
$ApplicationPath = Join-Path $DistPath "Peaceful Poker"
$Exe = Join-Path $ApplicationPath "Peaceful Poker.exe"
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
$Architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
if ($Architecture -ne "x64") {
    throw "The release ZIP naming currently requires an x64 build; detected $Architecture."
}
$ZipPath = Join-Path $DistPath "Peaceful-Poker-$Version-Windows-x64.zip"
$ZipFullPath = [System.IO.Path]::GetFullPath($ZipPath)
$DistPrefix = [System.IO.Path]::GetFullPath($DistPath).TrimEnd('\') + '\'
if (-not $ZipFullPath.StartsWith($DistPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace an archive outside the distribution directory: $ZipFullPath"
}
if (Test-Path -LiteralPath $ZipFullPath) {
    Remove-Item -Force -LiteralPath $ZipFullPath
}

Compress-Archive -LiteralPath $ApplicationPath -DestinationPath $ZipFullPath -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $ZipFullPath -PathType Leaf)) {
    throw "Portable ZIP was not created: $ZipFullPath"
}
$Archive = Get-Item -LiteralPath $ZipFullPath
$Checksum = (Get-FileHash -LiteralPath $ZipFullPath -Algorithm SHA256).Hash
Write-Host "Portable ZIP: $($Archive.FullName)"
Write-Host ("Size: {0:N0} bytes ({1:N2} MiB)" -f $Archive.Length, ($Archive.Length / 1MB))
Write-Host "SHA-256: $Checksum"
