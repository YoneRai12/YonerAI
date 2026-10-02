$file = "src/cogs/ora.py"
$lines = Get-Content $file

# Intervals to remove (1-based index from outline, so 0-based is -1)
# _execute_tool: 1327 to 3508 -> Index 1326 to 3508 (inclusive)
# But let's verification buffer.
# Line 1327 starts with "    async def _execute_tool"
# Line 3512 starts with "    async def switch_brain"

# We will reconstruct the file line by line to be safe, or just filter.
$newLines = @()
$skip = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    
    # Start of _execute_tool
    if ($line -match "^\s*async def _execute_tool") {
        $skip = $true
        $newLines += "    # Legacy _execute_tool removed. See src/legacy/ora_legacy.py"
        Write-Host "Started stripping _execute_tool at line $($i+1)"
    }
    
    # End of _execute_tool (Start of switch_brain)
    if ($skip -and $line -match "^\s*async def switch_brain") {
        $skip = $false
        Write-Host "Stopped stripping at line $($i+1)"
    }

    if (-not $skip) {
        $newLines += $line
    }
}

$newLines | Set-Content $file -Encoding UTF8
Write-Host "Done stripping ora.py"
