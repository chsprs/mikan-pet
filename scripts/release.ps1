[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [Parameter(Mandatory = $true)]
    [string]$Message,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Standardize version format: e.g. 0.1.6
$cleanVersion = $Version.Trim().TrimStart('v', 'V')
if ($cleanVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must follow semantic format X.Y.Z (e.g. 0.1.6), got: $Version"
}

# Detect Python interpreter if not explicitly passed
if (-not $Python) {
    $venvPy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPy) {
        $Python = $venvPy
    } else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}

Write-Host "==> 1/5 Bumping version to $cleanVersion across 4 files..."
$pyproject = Join-Path $ProjectRoot 'pyproject.toml'
(Get-Content $pyproject -Raw) -replace '(?m)^version\s*=\s*"[^"]+"', "version = `"$cleanVersion`"" | Set-Content $pyproject -NoNewline

$initPy = Join-Path $ProjectRoot 'mikan_pet\__init__.py'
(Get-Content $initPy -Raw) -replace '(?m)^__version__\s*=\s*"[^"]+"', "__version__ = `"$cleanVersion`"" | Set-Content $initPy -NoNewline

$appPy = Join-Path $ProjectRoot 'mikan_pet\app.py'
(Get-Content $appPy -Raw) -replace '(?m)^VERSION\s*=\s*"[^"]+"', "VERSION = `"$cleanVersion`"" | Set-Content $appPy -NoNewline

$iss = Join-Path $ProjectRoot 'installer\MikanPet.iss'
(Get-Content $iss -Raw) -replace '(?m)#define MyAppVersion\s*"[^"]+"', "#define MyAppVersion `"$cleanVersion`"" | Set-Content $iss -NoNewline

Write-Host "==> 2/5 Running all unit tests..."
& $Python -m unittest discover -s (Join-Path $ProjectRoot 'tests')
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed! Aborting release."
}

Write-Host "==> 3/5 Staging and committing changes..."
git -C $ProjectRoot add -A
git -C $ProjectRoot commit -m "$Message"
if ($LASTEXITCODE -ne 0) {
    throw "Git commit failed!"
}

$tag = "v$cleanVersion"
Write-Host "==> 4/5 Tagging $tag..."
git -C $ProjectRoot tag $tag

Write-Host "==> 5/5 Pushing main and $tag to GitHub..."
git -C $ProjectRoot push origin main --tags
if ($LASTEXITCODE -ne 0) {
    throw "Git push failed!"
}

Write-Host "==> Release $tag pushed! GitHub Actions will build installer & portable zip."
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) diperlukan untuk membuktikan hasil rilis."
}
Write-Host "Menunggu status GitHub Actions..."
Start-Sleep -Seconds 5
$runId = (gh run list --workflow=release.yml --limit=1 --json databaseId -q '.[0].databaseId')
if (-not $runId) {
    throw "Workflow rilis tidak ditemukan setelah tag $tag didorong."
}
Write-Host "Monitoring Run ID: $runId"
gh run watch $runId --exit-status
if ($LASTEXITCODE -ne 0) {
    throw "Workflow rilis gagal untuk tag $tag (Run ID: $runId)."
}

$assetNames = @(gh release view $tag --json assets --jq '.assets[].name')
if ($LASTEXITCODE -ne 0) {
    throw "GitHub Release $tag tidak dapat diverifikasi."
}
$requiredAssets = @(
    'MikanPet-Setup-x64.exe',
    'MikanPet-portable-x64.zip',
    'MikanPet-Setup-arm64.exe',
    'MikanPet-portable-arm64.zip',
    'SHA256SUMS.txt'
)
$missingAssets = @($requiredAssets | Where-Object { $_ -notin $assetNames })
if ($missingAssets.Count -gt 0) {
    throw "Rilis $tag tidak lengkap. Aset hilang: $($missingAssets -join ', ')"
}
Write-Host "==> Rilis $tag selesai, lengkap, dan siap diunduh pengguna via auto-updater!"
