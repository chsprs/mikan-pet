[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Installer,
    [Parameter(Mandatory = $true)]
    [string]$InstallDirectory
)

$ErrorActionPreference = 'Stop'
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
if (-not $env:RUNNER_TEMP) {
    throw 'Installer smoke testing is restricted to an isolated CI runner.'
}
$runnerRoot = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd([char[]]@('\', '/'))
$installPath = [IO.Path]::GetFullPath($InstallDirectory)
$runnerPrefix = $runnerRoot + [IO.Path]::DirectorySeparatorChar
if (-not $installPath.StartsWith($runnerPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Install directory must stay inside RUNNER_TEMP: $installPath"
}

$uninstaller = Join-Path $installPath 'unins000.exe'
try {
    $install = Start-Process -FilePath $installerPath -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=$installPath"
    ) -Wait -PassThru
    if ($install.ExitCode -ne 0) {
        throw "Installer exited with code $($install.ExitCode)."
    }
    $executable = Join-Path $installPath 'MikanPet.exe'
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "Installed executable was not found: $executable"
    }
    $smoke = Start-Process -FilePath $executable -ArgumentList '--smoke-test' -Wait -PassThru
    if ($smoke.ExitCode -ne 0) {
        throw "Installed smoke test exited with code $($smoke.ExitCode)."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $installPath 'version.txt'))) {
        throw 'Installed version metadata is missing.'
    }
}
finally {
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
        ) -Wait -PassThru
        if ($uninstall.ExitCode -ne 0) {
            throw "Uninstaller exited with code $($uninstall.ExitCode)."
        }
    }
}

if (Test-Path -LiteralPath (Join-Path $installPath 'MikanPet.exe')) {
    throw 'Uninstall smoke test left MikanPet.exe behind.'
}
Write-Host "Installer smoke test passed: $installerPath"
