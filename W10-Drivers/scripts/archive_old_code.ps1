# Archive Old Automation Code
#
# Moves the old automation code to an archive folder for safe keeping.
# Does NOT delete anything - just moves to dated archive folder.
#
# Run with: PowerShell -ExecutionPolicy Bypass -File archive_old_code.ps1

$ErrorActionPreference = "Continue"

$date = Get-Date -Format "yyyyMMdd-HHmmss"
$archivePath = "C:\Archive-$date"

Write-Host "=" * 70
Write-Host "Archiving Old Automation Code"
Write-Host "=" * 70
Write-Host ""
Write-Host "Archive location: $archivePath"
Write-Host ""

# Create archive directory
New-Item -ItemType Directory -Path $archivePath -Force | Out-Null

Write-Host "Created archive directory"
Write-Host ""

# =============================================================================
# Define what to archive
# =============================================================================

$itemsToArchive = @(
    @{
        Path = "C:\SocialWorker"
        Name = "SocialWorker"
        Description = "Python automation scripts (fetcher, poster, OSP GUI)"
    },
    @{
        Path = "C:\Automation"
        Name = "Automation"
        Description = "General automation folder"
    },
    @{
        Path = "C:\OSP"
        Name = "OSP"
        Description = "On-Screen Prompter system"
    }
)

# =============================================================================
# Archive items
# =============================================================================

$archived = 0
$skipped = 0

foreach ($item in $itemsToArchive) {
    if (Test-Path $item.Path) {
        Write-Host "[$($archived + $skipped + 1)/$($itemsToArchive.Count)] Archiving: $($item.Name)"
        Write-Host "  From: $($item.Path)"
        
        $destPath = Join-Path $archivePath $item.Name
        
        try {
            Move-Item -Path $item.Path -Destination $destPath -Force
            Write-Host "  ✓ Archived to: $destPath" -ForegroundColor Green
            $archived++
        } catch {
            Write-Host "  ✗ Failed to archive: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "[$($archived + $skipped + 1)/$($itemsToArchive.Count)] Skipping: $($item.Name)"
        Write-Host "  - Not found at: $($item.Path)" -ForegroundColor Gray
        $skipped++
    }
    Write-Host ""
}

# =============================================================================
# Archive Chrome extension (just copy, don't move)
# =============================================================================

Write-Host "Archiving Chrome extension..."

$extensionSources = @(
    "C:\ChromeExtension",
    "$env:USERPROFILE\Documents\ChromeExtension",
    "C:\Users\Public\Documents\ChromeExtension"
)

$extensionFound = $false
foreach ($source in $extensionSources) {
    if (Test-Path $source) {
        Write-Host "  Found at: $source"
        $destPath = Join-Path $archivePath "ChromeExtension"
        Copy-Item -Path $source -Destination $destPath -Recurse -Force
        Write-Host "  ✓ Copied to archive" -ForegroundColor Green
        $extensionFound = $true
        break
    }
}

if (!$extensionFound) {
    Write-Host "  - Chrome extension source not found (may already be archived)" -ForegroundColor Gray
}

Write-Host ""

# =============================================================================
# Create archive info file
# =============================================================================

$infoFile = Join-Path $archivePath "ARCHIVE_INFO.txt"

$infoContent = @"
ARCHIVE CREATED: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

This archive contains the OLD automation system components that were
replaced by the new Ubuntu-based architecture.

Contents:
---------
$( ($itemsToArchive | ForEach-Object { "- $($_.Name): $($_.Description)" }) -join "`n" )

Reason for Archive:
-------------------
Architectural shift from Windows-based AI automation to Ubuntu-based
deterministic workflows. Windows 10 is now a passive "cockpit" that
receives commands from Ubuntu.

How to Restore (if needed):
----------------------------
1. Move items from this archive back to their original locations
2. Run install_services.ps1 in SocialWorker folder
3. Enable scheduled tasks
4. Restart services

Do NOT restore unless:
- You're reverting to the old architecture
- You need to reference old code
- Testing/debugging purposes

Related Documentation:
----------------------
- See W10-Drivers/docs/W10-SIMPLER-COCPIT.md for new architecture
- See Ubu-Cont/docs/UBU-PY-VISION-NEW.md for Ubuntu implementation

"@

Set-Content -Path $infoFile -Value $infoContent

Write-Host "Created archive info file: $infoFile"
Write-Host ""

# =============================================================================
# Summary
# =============================================================================

Write-Host "=" * 70
Write-Host "ARCHIVAL COMPLETE"
Write-Host "=" * 70
Write-Host ""
Write-Host "Summary:"
Write-Host "  ✓ Archived: $archived items"
Write-Host "  - Skipped:  $skipped items (not found)"
Write-Host ""
Write-Host "Archive location: $archivePath"
Write-Host "Archive size: $([math]::Round((Get-ChildItem $archivePath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 2)) MB"
Write-Host ""
Write-Host "What was archived:"
foreach ($item in $itemsToArchive) {
    $itemPath = Join-Path $archivePath $item.Name
    if (Test-Path $itemPath) {
        Write-Host "  ✓ $($item.Name)" -ForegroundColor Green
    }
}
Write-Host ""
Write-Host "IMPORTANT: Nothing was deleted - all code is safely archived"
Write-Host ""
Write-Host "To restore: Move items from $archivePath back to C:\"
Write-Host ""
Write-Host "=" * 70
