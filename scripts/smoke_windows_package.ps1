[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ApplicationDirectory,
    [string] $SmokeRoot = (Join-Path ([System.IO.Path]::GetTempPath()) "PeacefulPokerReleaseSmoke")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:OS -ne "Windows_NT") {
    throw "The packaged Windows smoke test must run on Windows."
}

$ApplicationDirectory = (Resolve-Path $ApplicationDirectory -ErrorAction Stop).Path
$Exe = Join-Path $ApplicationDirectory "Peaceful Poker.exe"
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw "Missing packaged executable: $Exe"
}

$PlatformPlugins = @(Get-ChildItem -LiteralPath $ApplicationDirectory -Recurse -Filter "qwindows.dll")
if ($PlatformPlugins.Count -ne 1) {
    throw "Expected exactly one bundled qwindows.dll; found $($PlatformPlugins.Count)."
}

$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$SmokeRoot = [System.IO.Path]::GetFullPath($SmokeRoot).TrimEnd('\')
if (-not ($SmokeRoot + '\').StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Smoke output must remain under the system temporary directory: $SmokeRoot"
}
if (Test-Path -LiteralPath $SmokeRoot) {
    Remove-Item -Recurse -Force -LiteralPath $SmokeRoot
}
New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null

$EnvironmentNames = @(
    "LOCALAPPDATA",
    "PEACEFUL_POKER_SMOKE_REPORT",
    "PEACEFUL_POKER_SMOKE_TEST",
    "PEACEFUL_POKER_AUTOCLOSE_MS",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_QPA_PLATFORM"
)
$OriginalEnvironment = @{}
foreach ($Name in $EnvironmentNames) {
    $OriginalEnvironment[$Name] = [System.Environment]::GetEnvironmentVariable($Name, "Process")
}

function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Test-SmokeReport([string] $ReportPath, [bool] $ExpectExistingSettings) {
    Assert-True (Test-Path -LiteralPath $ReportPath -PathType Leaf) "Packaged smoke report was not created: $ReportPath"
    $Smoke = Get-Content -Raw -LiteralPath $ReportPath | ConvertFrom-Json
    if ($null -ne $Smoke.PSObject.Properties["smoke_error"]) {
        throw "Packaged smoke reported an error: $($Smoke.smoke_error)"
    }

    $RequiredFlags = @(
        "executable_launched",
        "landing_page_loaded",
        "frozen",
        "themes_loaded",
        "analysis_complete",
        "action_aware_complete",
        "resources_loaded",
        "save_round_trip",
        "settings_writable",
        "exports_written",
        "terminology_loaded",
        "terminology_single_layout",
        "training_started",
        "action_labels_contextual",
        "clean_close"
    )
    foreach ($Name in $RequiredFlags) {
        Assert-True ([bool] $Smoke.$Name) "Packaged smoke check failed: $Name"
    }
    Assert-True ($Smoke.window_title -eq "Peaceful Poker") "The packaged window title is incorrect."
    Assert-True ([int] $Smoke.terminology_count -gt 0) "Terminology data was empty."
    Assert-True (Test-Path -LiteralPath $Smoke.saved_hand -PathType Leaf) "The smoke save file is missing."
    Assert-True (Test-Path -LiteralPath $Smoke.settings_file -PathType Leaf) "The smoke settings file is missing."
    Assert-True (Test-Path -LiteralPath $Smoke.markdown_export -PathType Leaf) "The Markdown export is missing."
    Assert-True (Test-Path -LiteralPath $Smoke.json_export -PathType Leaf) "The JSON export is missing."
    Assert-True (Test-Path -LiteralPath $Smoke.log_file -PathType Leaf) "The packaged log file is missing."
    Assert-True ([bool] $Smoke.settings_existed_at_start -eq $ExpectExistingSettings) "Settings persistence did not match the expected launch state."

    $UserData = [System.IO.Path]::GetFullPath([string] $Smoke.user_data_dir).TrimEnd('\') + '\'
    $ApplicationPrefix = $ApplicationDirectory.TrimEnd('\') + '\'
    Assert-True (-not $UserData.StartsWith($ApplicationPrefix, [System.StringComparison]::OrdinalIgnoreCase)) "User data was written inside the application directory."
    return $Smoke
}

try {
    [System.Environment]::SetEnvironmentVariable("QT_PLUGIN_PATH", $null, "Process")
    [System.Environment]::SetEnvironmentVariable("QT_QPA_PLATFORM_PLUGIN_PATH", $null, "Process")
    [System.Environment]::SetEnvironmentVariable("QT_QPA_PLATFORM", $null, "Process")
    [System.Environment]::SetEnvironmentVariable("PEACEFUL_POKER_AUTOCLOSE_MS", $null, "Process")
    $env:LOCALAPPDATA = Join-Path $SmokeRoot "LocalAppData"
    $env:PEACEFUL_POKER_SMOKE_TEST = "1"

    for ($Launch = 1; $Launch -le 2; $Launch++) {
        $Report = Join-Path $SmokeRoot "packaged-smoke-$Launch.json"
        $env:PEACEFUL_POKER_SMOKE_REPORT = $Report
        $Process = Start-Process -FilePath $Exe -WorkingDirectory $SmokeRoot -PassThru
        if (-not $Process.WaitForExit(120000)) {
            $Process.Kill()
            $Process.WaitForExit()
            throw "Packaged application did not finish smoke launch $Launch within 120 seconds."
        }
        if ($Process.ExitCode -ne 0) {
            throw "Packaged application smoke launch $Launch exited with $($Process.ExitCode)."
        }
        $Smoke = Test-SmokeReport $Report ($Launch -eq 2)
        Write-Host "Packaged smoke launch $Launch passed: $Report"
    }

    Write-Host "Packaged smoke verification passed with Qt development variables cleared."
}
finally {
    foreach ($Name in $EnvironmentNames) {
        [System.Environment]::SetEnvironmentVariable($Name, $OriginalEnvironment[$Name], "Process")
    }
}
