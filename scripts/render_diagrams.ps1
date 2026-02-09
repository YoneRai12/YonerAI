Param(
  [int]$Scale = 6
)

$ErrorActionPreference = "Stop"

Write-Host "Rendering Mermaid diagrams to PNG+SVG (scale=$Scale)..."

$files = Get-ChildItem -Path "docs/diagrams" -Filter "*.mmd"
if (-not $files) {
  Write-Host "No .mmd files found under docs/diagrams"
  exit 0
}

foreach ($f in $files) {
  $base = $f.FullName.Substring(0, $f.FullName.Length - 4)

  # Use a deterministic background per mode so diagrams remain readable on GitHub.
  # We render separate *_dark.mmd variants and match them here.
  $bg = "#f8fafc"
  # Regex is .NET; in PowerShell strings, backslash isn't special, so use `\.` not `\\.`.
  if ($f.Name -match "_dark\.mmd$") {
    $bg = "#0b1220"
  }

  # Quote the color so Windows/Pwsh/CMD wrappers never eat the leading '#'
  npx -y @mermaid-js/mermaid-cli@latest -i $f.FullName -o ($base + ".png") -b "$bg" -s $Scale --quiet
  npx -y @mermaid-js/mermaid-cli@latest -i $f.FullName -o ($base + ".svg") -b "$bg" --quiet
}

Write-Host "Done."
