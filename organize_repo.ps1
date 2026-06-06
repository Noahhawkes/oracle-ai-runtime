# Organizes Noah.Self Upload Repository into logical subfolders.
# SAFE: only moves files, never deletes. The 4 Oracle priority docs stay at root.

$repo = "G:\My Drive\HawkesNest LLC\ORACLE.AI\Users\Noah.Self\Noah.Self Upload Repository"

# Subfolders to create
$dirs = @("Resumes", "Journals", "RenderedReality", "Profile", "Legal", "Assets", "Archive")
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path "$repo\$d" | Out-Null
}

# Files Oracle depends on — DO NOT MOVE
$protected = @(
    "Noah.Identity.Anchor.json",
    "Noah_Hawkes_Complete_Profile.docx",
    "Noah_Hawkes_Narrative_Profile.docx",
    "Updated_Noah_Personal_Mind_Journal.docx",
    "Updated_Noah_Business_Financial_Journal.docx",
    "Frequency_Anchor_120Hz.json"
)

function Move-Safe($file, $dest) {
    $name = Split-Path $file -Leaf
    if ($protected -contains $name) {
        Write-Host "  [PROTECTED] $name — skipped"
        return
    }
    $target = Join-Path $dest $name
    if (Test-Path $target) {
        Write-Host "  [SKIP] $name already at destination"
        return
    }
    Move-Item -Path $file -Destination $target
    Write-Host "  [MOVED] $name -> $(Split-Path $dest -Leaf)\"
}

Write-Host "`n=== Organizing Noah.Self Upload Repository ===`n"

# Resumes
foreach ($f in Get-ChildItem "$repo\Noah_Hawkes_Resume*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Resumes" }
foreach ($f in Get-ChildItem "$repo\NoahHawkes*Cover*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Resumes" }

# Rendered Reality
foreach ($f in Get-ChildItem "$repo\Rendered*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\RenderedReality" }
foreach ($f in Get-ChildItem "$repo\Rendered_Reality*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\RenderedReality" }
foreach ($f in Get-ChildItem "$repo\Updated_Fully_Restored_Drakin*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\RenderedReality" }

# Journals
foreach ($f in Get-ChildItem "$repo\Updated_Noah_*Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\Updated_Noah_*Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\Noah Personal Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\ashley_threaded_journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\VIRUS_420to120*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\Updated_Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\Updated_Noah_Author_Books_Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }
foreach ($f in Get-ChildItem "$repo\Updated_Noah_Family_Journal*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Journals" }

# Profile / Identity docs
foreach ($f in Get-ChildItem "$repo\Noah's Full*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\MirrorThread*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\Chat history*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\Thread*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\thread*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\Noah_Hawkes_Narrative_Profile*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\Noah_Hawkes_Complete_Profile*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }
foreach ($f in Get-ChildItem "$repo\Opportunity_Tracking*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Profile" }

# Legal / sensitive
foreach ($f in Get-ChildItem "$repo\Noah social security*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Legal" }
foreach ($f in Get-ChildItem "$repo\Noah- Texas*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Legal" }
foreach ($f in Get-ChildItem "$repo\Noah recomendation*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Legal" }

# Assets
foreach ($f in Get-ChildItem "$repo\Noah signature*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Assets" }

# Archive (old pyz files, duplicates)
foreach ($f in Get-ChildItem "$repo\oracle_self_core*" -ErrorAction SilentlyContinue) { Move-Safe $f.FullName "$repo\Archive" }

Write-Host "`n=== Done. Files remaining at root: ==="
Get-ChildItem "$repo" -File | Select-Object -ExpandProperty Name
