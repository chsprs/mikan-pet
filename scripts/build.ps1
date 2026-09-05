[CmdletBinding()]
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [ValidateSet('x64', 'arm64')]
    [string]$Architecture = 'x64',
    [switch]$SkipInstaller,
    [string]$SigningCertificatePath = '',
    [string]$SigningCertificatePassword = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
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

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $kitsRoot = 'C:\Program Files (x86)\Windows Kits\10\bin'
    if (-not (Test-Path -LiteralPath $kitsRoot)) {
        throw 'signtool.exe was not found in PATH or the Windows SDK.'
    }
    $toolArchitecture = if ($Architecture -eq 'arm64') { 'arm64' } else { 'x64' }
    $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter signtool.exe -File -Recurse |
        Where-Object { $_.Directory.Name -eq $toolArchitecture } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        throw "signtool.exe for $toolArchitecture was not found in the Windows SDK."
    }
    return $candidate.FullName
}

function Invoke-CodeSigning([string]$Target) {
    if (-not $SigningCertificatePath) {
        return
    }
    if (-not (Test-Path -LiteralPath $SigningCertificatePath)) {
        throw "Signing certificate was not found: $SigningCertificatePath"
    }
    $signTool = Find-SignTool
    & $signTool sign /fd SHA256 /tr $TimestampUrl /td SHA256 /f $SigningCertificatePath /p $SigningCertificatePassword $Target
    if ($LASTEXITCODE -ne 0) {
        throw "Authenticode signing failed for: $Target"
    }
    & $signTool verify /pa $Target
    if ($LASTEXITCODE -ne 0) {
        throw "Authenticode verification failed for: $Target"
    }
}

Push-Location $ProjectRoot
try {
    $pythonInfo = & $Python -c 'import platform, struct, sys; print(str(struct.calcsize(chr(80)) * 8), platform.machine(), sys.version, sep=chr(124))'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect selected Python interpreter: $Python"
    }
    $parts = $pythonInfo -split '\|', 3
    $expectedMachines = if ($Architecture -eq 'arm64') { @('ARM64', 'AARCH64') } else { @('AMD64', 'X86_64') }
    if ($parts.Count -ne 3 -or $parts[0] -ne '64' -or $parts[1].ToUpperInvariant() -notin $expectedMachines) {
        throw "Selected Python must be a 64-bit $Architecture interpreter; got: $pythonInfo"
    }
    Write-Host "Python: $Python ($($parts[1]), $($parts[2]))"

    Invoke-Checked $Python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    $buildDirectory = Join-Path $ProjectRoot 'build'
    $applicationDirectory = Join-Path $ProjectRoot 'dist\MikanPet'
    $portableZip = Join-Path $ProjectRoot "dist\MikanPet-portable-$Architecture.zip"
    $installer = Join-Path $ProjectRoot "dist\MikanPet-Setup-$Architecture.exe"
    $specFile = Join-Path $ProjectRoot 'MikanPet.spec'
    foreach ($target in @($buildDirectory, $applicationDirectory, $portableZip, $installer, $specFile)) {
        Remove-RepositoryItem $target
    }

    Invoke-Checked $Python @((Join-Path $ProjectRoot 'scripts\generate_icon.py'))
    $appVersion = (& $Python -c "import mikan_pet; print(mikan_pet.__version__)").Trim()
    $versionInfoFile = Join-Path $buildDirectory 'MikanPet-version-info.txt'
    Invoke-Checked $Python @(
        (Join-Path $ProjectRoot 'scripts\generate_version_info.py'),
        $appVersion,
        $versionInfoFile
    )

    Invoke-Checked $Python @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed', '--name', 'MikanPet',
        '--hidden-import', 'win32gui', '--hidden-import', 'win32con',
        '--paths', $ProjectRoot, '--manifest', (Join-Path $ProjectRoot 'packaging\MikanPet.manifest'),
        '--version-file', $versionInfoFile,
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
    $expectedPeMachine = if ($Architecture -eq 'arm64') { 0xAA64 } else { 0x8664 }
    if ($machine -ne $expectedPeMachine) {
        throw ('Built executable must have PE Machine 0x{0:X4}; got 0x{1:X4}' -f $expectedPeMachine, $machine)
    }
    Write-Host ('PE Machine: 0x{0:X4}' -f $machine)
    [IO.File]::WriteAllText(
        (Join-Path $applicationDirectory 'version.txt'),
        "$appVersion`r`n",
        [Text.Encoding]::ASCII
    )
    Invoke-CodeSigning $executable
    Invoke-Checked $executable @('--smoke-test')
    Invoke-Checked $Python @((Join-Path $ProjectRoot 'scripts\verify_gui_smoke.py'), $executable)

    Compress-Archive -Path (Join-Path $applicationDirectory '*') -DestinationPath $portableZip -Force
    if (-not (Test-Path -LiteralPath $portableZip) -or (Get-Item -LiteralPath $portableZip).Length -le 0) {
        throw "Portable archive was not created: $portableZip"
    }

    if (-not $SkipInstaller) {
        $iscc = Find-Iscc
        Invoke-Checked $iscc @(
            "/DMyAppVersion=$appVersion",
            "/DMyArchitecture=$Architecture",
            '/Qp',
            (Join-Path $ProjectRoot 'installer\MikanPet.iss')
        )
        if (-not (Test-Path -LiteralPath $installer) -or (Get-Item -LiteralPath $installer).Length -le 0) {
            throw "Installer was not created: $installer"
        }
        Invoke-CodeSigning $installer
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
