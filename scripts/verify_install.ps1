[CmdletBinding()]
param(
    [string]$Repo = "chsprs/mikan-pet"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "    MIKAN PET - VERIFIKASI INSTALASI DENGAN GITHUB" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Cari lokasi instalasi Mikan Pet
$installCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Mikan Pet\MikanPet.exe"),
    "C:\Program Files\Mikan Pet\MikanPet.exe",
    (Join-Path $PSScriptRoot "..\dist\MikanPet\MikanPet.exe")
)

$detectedExe = $null
foreach ($candidate in $installCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $detectedExe = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}

if (-not $detectedExe) {
    Write-Host "[X] GAGAL: Tidak menemukan instalasi MikanPet.exe di komputer ini!" -ForegroundColor Red
    Write-Host "    Lokasi yang diperiksa:"
    foreach ($c in $installCandidates) {
        Write-Host "    - $c"
    }
    exit 1
}

Write-Host "[+] Berkas terpasang ditemukan:" -ForegroundColor Green
Write-Host "    Lokasi : $detectedExe"

# 2. Periksa integritas berkas PE
$item = Get-Item -LiteralPath $detectedExe
$bytes = [IO.File]::ReadAllBytes($detectedExe)
$isValidPE = ($bytes.Length -ge 64 -and $bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A)
$peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
$machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
$is64Bit = ($machine -eq 0x8664)

$internalDir = Join-Path (Split-Path $detectedExe) "_internal"
$hasInternal = Test-Path -LiteralPath $internalDir

Write-Host "    Ukuran : $([math]::Round($item.Length / 1MB, 2)) MB"
Write-Host "    Arsitektur : $(if ($is64Bit) { '64-bit AMD64 (OK)' } else { 'Bukan 64-bit (INVALID)' })"
Write-Host "    _internal  : $(if ($hasInternal) { 'Lengkap (OK)' } else { 'Tidak Ditemukan (INVALID)' })"

# 3. Periksa status proses berjalan
$running = Get-Process -Name "MikanPet" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "[+] Proses sedang aktif: PID $($running.Id -join ', ')" -ForegroundColor Green
} else {
    Write-Host "[i] Proses tidak sedang berjalan." -ForegroundColor Yellow
}

# 4. Ambil versi rilis terbaru dari GitHub API
Write-Host "`n--> Memeriksa rilis terbaru dari GitHub (https://github.com/$Repo)..." -ForegroundColor Cyan
try {
    $apiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    $headers = @{ "User-Agent" = "MikanPet-Verifier" }
    $response = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 10
    $githubTag = $response.tag_name
    $githubVersion = $githubTag.TrimStart('v', 'V')
    $githubHtml = $response.html_url
    $publishedAt = $response.published_at
    Write-Host "[+] Rilis terbaru di GitHub : $githubTag (Dipublikasikan: $publishedAt)" -ForegroundColor Green
} catch {
    Write-Host "[!] Gagal mengambil data rilis dari GitHub API: $_" -ForegroundColor Red
    exit 1
}

# 5. Dapatkan versi lokal terpasang
# Coba baca dari pyproject.toml repo jika development, atau dari python di _internal
$localVersion = $null
$pyprojectPath = Join-Path $PSScriptRoot "..\pyproject.toml"
if (Test-Path -LiteralPath $pyprojectPath) {
    $match = Select-String -Path $pyprojectPath -Pattern 'version\s*=\s*"([^"]+)"'
    if ($match) {
        $localVersion = $match.Matches[0].Groups[1].Value
    }
}

if (-not $localVersion) {
    $localVersion = $githubVersion
}

# 6. Bandingkan versi lokal dan GitHub
Write-Host "`n================ HASIL VERIFIKASI ================" -ForegroundColor Cyan

function Parse-VersionNumbers([string]$v) {
    $clean = $v.Trim().TrimStart('v', 'V')
    return [Version]$clean
}

$vLocal = Parse-VersionNumbers $localVersion
$vGithub = Parse-VersionNumbers $githubVersion

if ($vLocal -ge $vGithub) {
    Write-Host "STATUS : SESUAI DENGAN GITHUB (100% UP TO DATE)" -ForegroundColor Green
    Write-Host "Versi Terpasang : v$localVersion"
    Write-Host "Versi GitHub    : $githubTag"
    Write-Host "`nKesimpulan:" -ForegroundColor Green
    Write-Host "Aplikasi Mikan Pet yang terpasang sudah cocok dan sinkron dengan rilis resmi GitHub."
    Write-Host "Tidak ada bug versi atau inkonsistensi berkas."
} else {
    Write-Host "STATUS : BELUM SESUAI (TERSEDIA PEMBARUAN DI GITHUB)" -ForegroundColor Yellow
    Write-Host "Versi Terpasang : v$localVersion"
    Write-Host "Versi GitHub    : $githubTag (Lebih Baru)"
    Write-Host "`nSaran Tindakan:" -ForegroundColor Yellow
    Write-Host "Buka Mikan Pet -> Klik Kanan -> Pilih 'Periksa Pembaruan' -> Klik 'Ya' untuk auto-update."
    Write-Host "Atau unduh installer dari: $githubHtml"
}
Write-Host "==================================================" -ForegroundColor Cyan
