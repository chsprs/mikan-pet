[CmdletBinding()]
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectRootPrefix = $ProjectRoot.TrimEnd([char[]]@('\', '/')) + [IO.Path]::DirectorySeparatorChar

function Assert-RepositoryPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($ProjectRootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete a path outside the repository: $fullPath"
    }
    return $fullPath
}

function Remove-RepositoryItem([string]$Path) {
    $fullPath = Assert-RepositoryPath $Path
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Force -Recurse
    }
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

function Find-Iscc {
    $candidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        'C:\Program Files\Inno Setup 7\ISCC.exe',
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    )
    $uniqueCandidates = [Collections.Generic.List[string]]::new()
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $resolved = (Resolve-Path -LiteralPath $candidate).Path
            if (-not $uniqueCandidates.Exists([Predicate[string]] {
                param($existing)
                [string]::Equals($existing, $resolved, [StringComparison]::OrdinalIgnoreCase)
            })) {
                $uniqueCandidates.Add($resolved)
            }
        }
    }
    if ($uniqueCandidates.Count -ne 1) {
        throw "Expected exactly one usable ISCC.exe, found $($uniqueCandidates.Count)."
    }
    return $uniqueCandidates[0]
}

Push-Location $ProjectRoot
try {
    $pythonInfo = & $Python -c 'import platform, struct, sys; print(str(struct.calcsize(chr(80)) * 8), platform.machine(), sys.version, sep=chr(124))'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect selected Python interpreter: $Python"
    }
    $parts = $pythonInfo -split '\|', 3
    if ($parts.Count -ne 3 -or $parts[0] -ne '64' -or $parts[1].ToUpperInvariant() -notin @('AMD64', 'X86_64')) {
        throw "Selected Python must be a 64-bit AMD64/x86_64 interpreter; got: $pythonInfo"
    }
    Write-Host "Python: $Python ($($parts[1]), $($parts[2]))"

    Invoke-Checked $Python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    Invoke-Checked $Python @((Join-Path $ProjectRoot 'scripts\generate_icon.py'))

    $buildDirectory = Join-Path $ProjectRoot 'build'
    $applicationDirectory = Join-Path $ProjectRoot 'dist\MikanPet'
    $portableZip = Join-Path $ProjectRoot 'dist\MikanPet-portable-x64.zip'
    $installer = Join-Path $ProjectRoot 'dist\MikanPet-Setup-x64.exe'
    $specFile = Join-Path $ProjectRoot 'MikanPet.spec'
    foreach ($target in @($buildDirectory, $applicationDirectory, $portableZip, $installer, $specFile)) {
        Remove-RepositoryItem $target
    }

    Invoke-Checked $Python @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed', '--name', 'MikanPet',
        '--hidden-import', 'win32gui', '--hidden-import', 'win32con',
        '--paths', $ProjectRoot, '--manifest', (Join-Path $ProjectRoot 'packaging\MikanPet.manifest'),
        '--icon', (Join-Path $ProjectRoot 'assets\MikanPet.ico'), (Join-Path $ProjectRoot 'mikan_pet\__main__.py')
    )

    $executable = Join-Path $applicationDirectory 'MikanPet.exe'
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "PyInstaller did not produce $executable"
    }
    $bytes = [IO.File]::ReadAllBytes($executable)
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
        throw "Built executable is not a valid PE file: $executable"
    }
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    if ($peOffset -lt 0 -or $peOffset + 6 -gt $bytes.Length -or $bytes[$peOffset] -ne 0x50 -or $bytes[$peOffset + 1] -ne 0x45) {
        throw "Built executable has an invalid PE header: $executable"
    }
    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    if ($machine -ne 0x8664) {
        throw ('Built executable must have PE Machine 0x8664; got 0x{0:X4}' -f $machine)
    }
    Write-Host ('PE Machine: 0x{0:X4}' -f $machine)
    Invoke-Checked $executable @('--smoke-test')
    Invoke-Checked $Python @((Join-Path $ProjectRoot 'scripts\verify_gui_smoke.py'), $executable)

    Compress-Archive -Path (Join-Path $applicationDirectory '*') -DestinationPath $portableZip -Force
    if (-not (Test-Path -LiteralPath $portableZip) -or (Get-Item -LiteralPath $portableZip).Length -le 0) {
        throw "Portable archive was not created: $portableZip"
    }

    if (-not $SkipInstaller) {
        $iscc = Find-Iscc
        Invoke-Checked $iscc @('/Qp', (Join-Path $ProjectRoot 'installer\MikanPet.iss'))
        if (-not (Test-Path -LiteralPath $installer) -or (Get-Item -LiteralPath $installer).Length -le 0) {
            throw "Installer was not created: $installer"
        }
    }

    $portableHash = (Get-FileHash -LiteralPath $portableZip -Algorithm SHA256).Hash
    Write-Host "SHA256 $portableZip $portableHash"
    if (-not $SkipInstaller) {
        $installerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
        Write-Host "SHA256 $installer $installerHash"
    }
}
finally {
    Pop-Location
}
