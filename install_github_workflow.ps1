$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root ".github\workflows"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath (Join-Path $root "github-workflows\update-and-deploy.yml") -Destination $target -Force
Copy-Item -LiteralPath (Join-Path $root "gitignore-template.txt") -Destination (Join-Path $root ".gitignore") -Force
Write-Host "GitHub Actions workflow installed: $target"
