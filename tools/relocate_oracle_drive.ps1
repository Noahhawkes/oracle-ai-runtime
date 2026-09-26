<#
Relocate ORACLE-related Drive roots into a D-drive runtime import area.

Default mode is DRY RUN. It writes a local relocation plan under state/ and
does not copy, rename, delete, sync, or mutate any source path unless -Execute
is supplied. Even in execute mode it copies first; originals are only renamed
to review archives when -ArchiveOriginals is also supplied.
#>
[CmdletBinding()]
param(
    [string]$DestinationRoot = "D:\Oracle\ORACLE.AI-runtime",
    [string[]]$SourceRoots = @(
        "G:\My Drive\ORACLE.AI",
        "G:\My Drive\OracleAI",
        "G:\My Drive\HawkesNest LLC\ORACLE.AI",
        "G:\My Drive\MiracleDrive_SealPhase_2025-04-05_16-44-46",
        "G:\My Drive\SOv1",
        "G:\My Drive\SOV1_Migration_2025",
        "G:\My Drive\LOGS",
        "G:\My Drive\Noah_Eternal_Rebuild",
        "G:\My Drive\NOAH_FlameAnchor_Deployment",
        "G:\My Drive\DOCX"
    ),
    [switch]$IncludeActiveRuntime,
    [switch]$Execute,
    [switch]$VerifyHash,
    [switch]$ArchiveOriginals
)

$ErrorActionPreference = "Stop"

function Get-FullPathSafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function ConvertTo-SafeFolderName {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = Get-FullPathSafe $Path
    return ($full -replace "[:\\\/\s]+", "_" -replace "[^A-Za-z0-9._-]", "_").Trim("_")
}

function Get-TreeStats {
    param([Parameter(Mandatory = $true)][string]$Path)
    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue)
    $bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $bytes) {
        $bytes = 0
    }
    return [pscustomobject]@{
        Files = $files.Count
        Bytes = [int64]$bytes
        GB    = [math]::Round(($bytes / 1GB), 3)
    }
}

function Assert-RelocationBoundary {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $sourceFull = (Get-FullPathSafe $Source).TrimEnd("\") + "\"
    $destFull = (Get-FullPathSafe $Destination).TrimEnd("\") + "\"
    if ($destFull.StartsWith($sourceFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destination is inside source. Refusing: $Source -> $Destination"
    }
    if ($sourceFull.StartsWith($destFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Source is inside destination. Refusing: $Source -> $Destination"
    }
}

function Test-CopyHash {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $mismatches = @()
    $sourceFiles = @(Get-ChildItem -LiteralPath $Source -Recurse -File -Force -ErrorAction SilentlyContinue)
    foreach ($file in $sourceFiles) {
        $relative = [System.IO.Path]::GetRelativePath($Source, $file.FullName)
        $target = Join-Path $Destination $relative
        if (-not (Test-Path -LiteralPath $target)) {
            $mismatches += [pscustomobject]@{ Path = $relative; Reason = "missing_target" }
            continue
        }
        $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ($sourceHash -ne $targetHash) {
            $mismatches += [pscustomobject]@{ Path = $relative; Reason = "sha256_mismatch" }
        }
    }
    return $mismatches
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$planDir = Join-Path $repoRoot "state\relocation"
New-Item -ItemType Directory -Force -Path $planDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$planPath = Join-Path $planDir "oracle_drive_relocation_plan_$stamp.json"

if ($IncludeActiveRuntime) {
    $SourceRoots += "C:\Oracle\ORACLE.AI-runtime"
}

$destinationFull = Get-FullPathSafe $DestinationRoot
$destinationDrive = [System.IO.Path]::GetPathRoot($destinationFull)
$destinationDriveExists = Test-Path -LiteralPath $destinationDrive
$importsRoot = [System.IO.Path]::Combine($destinationFull, "imported_roots")

$entries = @()
foreach ($source in ($SourceRoots | Select-Object -Unique)) {
    $exists = Test-Path -LiteralPath $source
    $entry = [ordered]@{
        source = $source
        exists = [bool]$exists
        destination = $null
        files = 0
        bytes = 0
        gb = 0
        planned_action = "skip_missing"
        executed = $false
        copy_exit_code = $null
        copied = $false
        hash_verified = $false
        hash_mismatches = @()
        archived_original = $false
        archive_path = $null
    }
    if ($exists) {
        $safe = ConvertTo-SafeFolderName $source
        $dest = [System.IO.Path]::Combine($importsRoot, $safe)
        Assert-RelocationBoundary -Source $source -Destination $dest
        $stats = Get-TreeStats $source
        $entry.destination = $dest
        $entry.files = $stats.Files
        $entry.bytes = $stats.Bytes
        $entry.gb = $stats.GB
        $entry.planned_action = "copy_to_imports_root"
        if ($Execute) {
            if (-not $destinationDriveExists) {
                throw "Destination drive is not mounted: $destinationDrive"
            }
            New-Item -ItemType Directory -Force -Path $dest | Out-Null
            $robocopyArgs = @($source, $dest, "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:2", "/W:2", "/XJ", "/NP")
            & robocopy @robocopyArgs | Out-Null
            $exit = $LASTEXITCODE
            $entry.copy_exit_code = $exit
            $entry.executed = $true
            if ($exit -le 7) {
                $entry.copied = $true
            } else {
                throw "Robocopy failed with exit code $exit for $source"
            }
            if ($VerifyHash) {
                $mismatches = @(Test-CopyHash -Source $source -Destination $dest)
                $entry.hash_mismatches = $mismatches
                $entry.hash_verified = ($mismatches.Count -eq 0)
                if ($mismatches.Count -gt 0) {
                    throw "Hash verification failed for $source"
                }
            }
            if ($ArchiveOriginals) {
                if ($source -ieq "C:\Oracle\ORACLE.AI-runtime") {
                    throw "Refusing to archive the active runtime while this script is running."
                }
                $archivePath = "$source.MOVED_TO_D_REVIEW_$stamp"
                if (Test-Path -LiteralPath $archivePath) {
                    throw "Archive target already exists: $archivePath"
                }
                Move-Item -LiteralPath $source -Destination $archivePath
                $entry.archived_original = $true
                $entry.archive_path = $archivePath
            }
        }
    }
    $entries += [pscustomobject]$entry
}

$plan = [ordered]@{
    ok = $true
    mode = if ($Execute) { "execute" } else { "dry_run" }
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    destination_root = $destinationFull
    destination_drive = $destinationDrive
    destination_drive_exists = [bool]$destinationDriveExists
    imports_root = $importsRoot
    include_active_runtime = [bool]$IncludeActiveRuntime
    verify_hash_requested = [bool]$VerifyHash
    archive_originals_requested = [bool]$ArchiveOriginals
    safety = [ordered]@{
        dry_run_default = $true
        deletes_originals = $false
        copies_before_archive = $true
        refuses_destination_inside_source = $true
        refuses_source_inside_destination = $true
        refuses_active_runtime_archive = $true
    }
    totals = [ordered]@{
        existing_roots = @($entries | Where-Object { $_.exists }).Count
        planned_files = ($entries | Measure-Object -Property files -Sum).Sum
        planned_bytes = ($entries | Measure-Object -Property bytes -Sum).Sum
        planned_gb = [math]::Round((($entries | Measure-Object -Property bytes -Sum).Sum / 1GB), 3)
    }
    entries = $entries
}

$plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $planPath -Encoding UTF8

Write-Host "ORACLE relocation plan written:"
Write-Host $planPath
Write-Host ""
$plan.totals | Format-List
Write-Host "Destination drive exists: $destinationDriveExists ($destinationDrive)"
if (-not $Execute) {
    Write-Host "DRY RUN ONLY: rerun with -Execute to copy. Add -VerifyHash to hash-check copies. Add -ArchiveOriginals only after review."
}
