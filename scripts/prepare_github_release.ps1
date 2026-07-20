[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "GitHub release assets for Peaceful Poker must be prepared on Windows."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectFile = Join-Path $Root "pyproject.toml"
$ProjectText = Get-Content -Raw -LiteralPath $ProjectFile
$VersionMatch = [regex]::Match($ProjectText, '(?m)^version\s*=\s*"([^"]+)"\s*$')
if (-not $VersionMatch.Success) {
    throw "Could not determine the application version from pyproject.toml."
}
$Version = $VersionMatch.Groups[1].Value

$DistDirectory = Join-Path $Root "dist"
$PortableSource = Join-Path $DistDirectory "Peaceful-Poker-$Version-Windows-x64.zip"
$InstallerSource = Join-Path $DistDirectory "installer\Peaceful-Poker-Setup-$Version.exe"
$ReleaseDirectory = Join-Path $DistDirectory "release"
$PortableAsset = Join-Path $ReleaseDirectory "Peaceful-Poker-Windows-x64.zip"
$InstallerAsset = Join-Path $ReleaseDirectory "Peaceful-Poker-Windows-Setup.exe"
$ChecksumFile = Join-Path $ReleaseDirectory "SHA256SUMS.txt"

if (-not (Test-Path -LiteralPath $PortableSource -PathType Leaf)) {
    throw "Required portable ZIP is missing: $PortableSource"
}

New-Item -ItemType Directory -Force -Path $ReleaseDirectory | Out-Null
foreach ($StaleAsset in @($PortableAsset, $InstallerAsset, $ChecksumFile)) {
    if (Test-Path -LiteralPath $StaleAsset) {
        Remove-Item -Force -LiteralPath $StaleAsset
    }
}

Copy-Item -LiteralPath $PortableSource -Destination $PortableAsset
$Assets = @($PortableAsset)
if (Test-Path -LiteralPath $InstallerSource -PathType Leaf) {
    Copy-Item -LiteralPath $InstallerSource -Destination $InstallerAsset
    $Assets += $InstallerAsset
}

$ChecksumLines = foreach ($Asset in $Assets) {
    $Hash = (Get-FileHash -LiteralPath $Asset -Algorithm SHA256).Hash
    "$Hash  $([System.IO.Path]::GetFileName($Asset))"
}
$Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($ChecksumFile, $ChecksumLines, $Utf8WithoutBom)

Write-Host "Peaceful Poker GitHub release assets prepared."
Write-Host "Version: $Version"
Write-Host "Portable source: $PortableSource"
if (Test-Path -LiteralPath $InstallerSource -PathType Leaf) {
    Write-Host "Installer source: $InstallerSource"
} else {
    Write-Host "Installer source: unavailable (portable release only)"
}
foreach ($Asset in $Assets) {
    $File = Get-Item -LiteralPath $Asset
    $Hash = (Get-FileHash -LiteralPath $Asset -Algorithm SHA256).Hash
    Write-Host "Asset: $($File.FullName)"
    Write-Host ("Size: {0:N0} bytes ({1:N2} MiB)" -f $File.Length, ($File.Length / 1MB))
    Write-Host "SHA-256: $Hash"
}
Write-Host "Checksums: $ChecksumFile"
