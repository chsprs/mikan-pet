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
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required to verify the release."
}
function Update-VersionFile([string]$Path, [string]$Pattern, [string]$Replacement) {
    $content = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) -replace $Pattern, $Replacement
    [IO.File]::WriteAllText($Path, $content, [Text.UTF8Encoding]::new($false))
}

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
Update-VersionFile $pyproject '(?m)^version\s*=\s*"[^"]+"' "version = `"$cleanVersion`""

$initPy = Join-Path $ProjectRoot 'mikan_pet\__init__.py'
Update-VersionFile $initPy '(?m)^__version__\s*=\s*"[^"]+"' "__version__ = `"$cleanVersion`""

$appPy = Join-Path $ProjectRoot 'mikan_pet\app.py'
Update-VersionFile $appPy '(?m)^VERSION\s*=\s*"[^"]+"' "VERSION = `"$cleanVersion`""

$iss = Join-Path $ProjectRoot 'installer\MikanPet.iss'
Update-VersionFile $iss '(?m)#define MyAppVersion\s*"[^"]+"' "#define MyAppVersion `"$cleanVersion`""

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
if ($LASTEXITCODE -ne 0) { throw "Could not create release tag $tag." }
$releaseCommit = (git -C $ProjectRoot rev-parse $tag).Trim()

Write-Host "==> 5/5 Pushing main and $tag to GitHub..."
git -C $ProjectRoot push origin main $tag
if ($LASTEXITCODE -ne 0) {
    throw "Git push failed!"
}

Write-Host "==> Release $tag pushed! GitHub Actions will build the Windows x64 installer."
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) diperlukan untuk membuktikan hasil rilis."
}
Write-Host "Menunggu status GitHub Actions..."
$runId = $null
for ($attempt = 0; $attempt -lt 12; $attempt++) {
    $runId = (gh run list --repo chsprs/mikan-pet --workflow release.yml --commit $releaseCommit --branch $tag --event push --limit 1 --json databaseId -q '.[0].databaseId')
    if ($LASTEXITCODE -ne 0) { throw "Could not query release workflow." }
    if ($runId) { break }
    Start-Sleep -Seconds 5
}
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
    'MikanPet-Setup-x64.exe'
)
$missingAssets = @($requiredAssets | Where-Object { $_ -notin $assetNames })
if ($missingAssets.Count -gt 0) {
    throw "Rilis $tag tidak lengkap. Aset hilang: $($missingAssets -join ', ')"
}
if ($assetNames.Count -ne 1) {
    throw "Rilis $tag melanggar kebijakan single-asset: ditemukan $($assetNames.Count) aset ($($assetNames -join ', '))"
}
Write-Host "==> Rilis $tag selesai, lengkap dengan single-asset MikanPet-Setup-x64.exe!"
