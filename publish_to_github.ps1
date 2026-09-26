$ErrorActionPreference = "Stop"
$repo = "HSC-Class01/JY_LGE"
$dashboard = "https://hsc-class01.github.io/JY_LGE/"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

gh auth status | Out-Null
& (Join-Path $root "install_github_workflow.ps1")

if (-not (Test-Path -LiteralPath (Join-Path $root ".git"))) {
    git init -b main
}

git add .
git -c user.name="HSC-Class01" -c user.email="github-actions[bot]@users.noreply.github.com" commit -m "feat: add LGE OpenDART financial agent"
if ($LASTEXITCODE -ne 0) {
    Write-Host "No new local changes to commit."
}

gh repo view $repo | Out-Null
if ($LASTEXITCODE -ne 0) {
    gh repo create $repo --public --source . --remote origin --push
} else {
    if (-not (git remote | Select-String -SimpleMatch "origin")) {
        git remote add origin "https://github.com/$repo.git"
    }
    git push -u origin main
}

gh repo edit $repo --homepage $dashboard
Write-Host "Published: https://github.com/$repo"
Write-Host "Next: add DART_API_KEY under Settings > Secrets and variables > Actions."
