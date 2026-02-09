Param(
  [int]$Scale = 5
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
  npx -y @mermaid-js/mermaid-cli@latest -i $f.FullName -o ($base + ".png") -b transparent -s $Scale --quiet
  npx -y @mermaid-js/mermaid-cli@latest -i $f.FullName -o ($base + ".svg") -b transparent --quiet
}

Write-Host "Done."

