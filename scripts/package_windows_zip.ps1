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

$QtPlugins = @(
    Get-ChildItem `
        -LiteralPath $ApplicationPath `
        -Recurse `
        -File `
        -Filter "qwindows.dll"
)

if ($QtPlugins.Count -ne 1) {
    throw "The application folder must contain exactly one qwindows.dll. Found $($QtPlugins.Count). Rebuild the application first."
}

$PyProjectPath = Join-Path $Root "pyproject.toml"

$VersionLine = Select-String `
    -LiteralPath $PyProjectPath `
    -Pattern '^\s*version\s*=\s*"([^"]+)"\s*$'

if ($VersionLine.Matches.Count -ne 1) {
    throw "Could not read exactly one release version from pyproject.toml."
}

$Version = $VersionLine.Matches[0].Groups[1].Value

# PROCESSOR_ARCHITEW6432 is present when 32-bit PowerShell runs on 64-bit Windows.
$RawArchitecture = if (-not [string]::IsNullOrWhiteSpace($env:PROCESSOR_ARCHITEW6432)) {
    $env:PROCESSOR_ARCHITEW6432
}
elseif (-not [string]::IsNullOrWhiteSpace($env:PROCESSOR_ARCHITECTURE)) {
    $env:PROCESSOR_ARCHITECTURE
}
elseif ([Environment]::Is64BitOperatingSystem) {
    "AMD64"
}
else {
    "x86"
}

$Architecture = switch ($RawArchitecture.ToUpperInvariant()) {
    "AMD64" { "x64" }
    "X64"   { "x64" }
    "ARM64" { "arm64" }
    "X86"   { "x86" }

    default {
        if ([Environment]::Is64BitOperatingSystem) {
            "x64"
        }
        else {
            "x86"
        }
    }
}

Write-Host "Detected architecture: $Architecture"

if ($Architecture -ne "x64") {
    throw "The release ZIP naming currently requires an x64 Windows build; detected $Architecture."
}

$ZipName = "Peaceful-Poker-$Version-Windows-x64.zip"
$ZipPath = Join-Path $DistPath $ZipName
$ZipFullPath = [System.IO.Path]::GetFullPath($ZipPath)

$DistFullPath = [System.IO.Path]::GetFullPath($DistPath)
$DistPrefix = $DistFullPath.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar

if (-not $ZipFullPath.StartsWith(
    $DistPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Refusing to replace an archive outside the distribution directory: $ZipFullPath"
}

if (Test-Path -LiteralPath $ZipFullPath) {
    Write-Host "Removing previous archive: $ZipFullPath"
    Remove-Item -LiteralPath $ZipFullPath -Force
}

Write-Host "Creating portable ZIP from:"
Write-Host "  $ApplicationPath"

Compress-Archive `
    -LiteralPath $ApplicationPath `
    -DestinationPath $ZipFullPath `
    -CompressionLevel Optimal

if (-not (Test-Path -LiteralPath $ZipFullPath -PathType Leaf)) {
    throw "Portable ZIP was not created: $ZipFullPath"
}

$Archive = Get-Item -LiteralPath $ZipFullPath
$Checksum = (
    Get-FileHash `
        -LiteralPath $ZipFullPath `
        -Algorithm SHA256
).Hash

Write-Host ""
Write-Host "Portable ZIP created successfully."
Write-Host "Path: $($Archive.FullName)"
Write-Host (
    "Size: {0:N0} bytes ({1:N2} MiB)" -f
    $Archive.Length,
    ($Archive.Length / 1MB)
)
Write-Host "SHA-256: $Checksum"