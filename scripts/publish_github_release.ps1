[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "Peaceful Poker GitHub releases must be published from Windows."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PrepareScript = Join-Path $PSScriptRoot "prepare_github_release.ps1"
$ProjectFile = Join-Path $Root "pyproject.toml"
$ProjectText = Get-Content -Raw -LiteralPath $ProjectFile
$VersionMatch = [regex]::Match($ProjectText, '(?m)^version\s*=\s*"([^"]+)"\s*$')
if (-not $VersionMatch.Success) {
    throw "Could not determine the application version from pyproject.toml."
}
$Version = $VersionMatch.Groups[1].Value
$Tag = "v$Version"

Push-Location $Root
try {
    $WorkingTree = @(git status --porcelain=v1)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the Git working tree."
    }
    if ($WorkingTree.Count -ne 0) {
        throw "The Git working tree must be clean before publishing.`n$($WorkingTree -join "`n")"
    }

    $Branch = (git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Branch) {
        throw "Publishing from a detached HEAD is not supported."
    }
    $Upstream = (git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Upstream) {
        throw "The current branch must have an upstream before publishing."
    }
    git fetch --quiet origin
    if ($LASTEXITCODE -ne 0) {
        throw "Could not refresh origin before checking synchronization."
    }
    $Counts = ((git rev-list --left-right --count "$Upstream...HEAD").Trim() -split '\s+')
    if ($LASTEXITCODE -ne 0 -or $Counts.Count -ne 2) {
        throw "Could not compare the current branch with $Upstream."
    }
    if ([int] $Counts[0] -ne 0 -or [int] $Counts[1] -ne 0) {
        throw "Branch $Branch is not synchronized with $Upstream. Pull or push first."
    }

    if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required. Install it from https://cli.github.com/."
    }
    gh auth status
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run: gh auth login"
    }

    & $PrepareScript

    $ReleaseDirectory = Join-Path $Root "dist\release"
    $PortableAsset = Join-Path $ReleaseDirectory "Peaceful-Poker-Windows-x64.zip"
    $InstallerAsset = Join-Path $ReleaseDirectory "Peaceful-Poker-Windows-Setup.exe"
    $ChecksumFile = Join-Path $ReleaseDirectory "SHA256SUMS.txt"
    if (-not (Test-Path -LiteralPath $PortableAsset -PathType Leaf)) {
        throw "Prepared portable asset is missing: $PortableAsset"
    }
    if (-not (Test-Path -LiteralPath $ChecksumFile -PathType Leaf)) {
        throw "Prepared checksum file is missing: $ChecksumFile"
    }

    git rev-parse --quiet --verify "refs/tags/$Tag" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Local tag $Tag does not exist. Create and push it before publishing."
    }
    $TagCommit = (git rev-list -n 1 $Tag).Trim()
    $HeadCommit = (git rev-parse HEAD).Trim()
    if ($TagCommit -ne $HeadCommit) {
        throw "Tag $Tag does not point to the current commit."
    }
    git ls-remote --exit-code --tags origin "refs/tags/$Tag" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Tag $Tag has not been pushed to origin."
    }

    $ExistingRelease = gh release view $Tag --json tagName,url,isDraft,isPrerelease 2>$null
    if ($LASTEXITCODE -eq 0) {
        throw "GitHub Release $Tag already exists. Refusing to overwrite it.`n$ExistingRelease"
    }

    $Assets = @($PortableAsset)
    $InstallerAvailable = Test-Path -LiteralPath $InstallerAsset -PathType Leaf
    if ($InstallerAvailable) {
        $Assets += $InstallerAsset
    }
    $Assets += $ChecksumFile

    $InstallerNote = if ($InstallerAvailable) {
        "- Windows installer: download Peaceful-Poker-Windows-Setup.exe and follow the prompts."
    } else {
        "- Windows installer: not included in this release."
    }
    $Notes = @"
Peaceful Poker $Version is an educational No-Limit Texas Hold'em decision trainer for Windows.

- Portable Windows: download Peaceful-Poker-Windows-x64.zip, extract it completely, then open Peaceful Poker.exe.
$InstallerNote
- Includes hand evaluation, showdown equity, action-aware analysis, Training, save/load, and exports.
- Python is not required for packaged downloads.
- This release is unsigned and may display a Windows reputation warning.

SHA-256 checksums are provided in SHA256SUMS.txt.
"@

    $Arguments = @(
        "release",
        "create",
        $Tag,
        "--verify-tag",
        "--latest",
        "--title",
        "Peaceful Poker $Version",
        "--notes",
        $Notes
    ) + $Assets
    gh @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub Release creation failed with exit code $LASTEXITCODE."
    }

    $ReleaseUrl = (gh release view $Tag --json url --jq '.url').Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ReleaseUrl) {
        throw "The release was created, but its URL could not be retrieved."
    }
    Write-Host "Published Peaceful Poker ${Version}: $ReleaseUrl"
}
finally {
    Pop-Location
}
