param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$specPath = Join-Path $root 'packaging\pyinstaller\zprint.spec'
$installerScript = Join-Path $root 'packaging\inno\zPrint.iss'

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec file not found at $specPath"
}

Write-Host 'Cleaning previous build output...' -ForegroundColor Cyan
$pyInstallerBuild = Join-Path $root 'build\zPrint'
$pyInstallerDist = Join-Path $root 'dist\zPrint'
if (Test-Path $pyInstallerBuild) {
    Remove-Item $pyInstallerBuild -Recurse -Force
}
if (Test-Path $pyInstallerDist) {
    Remove-Item $pyInstallerDist -Recurse -Force
}

Write-Host 'Running PyInstaller...' -ForegroundColor Cyan
pyinstaller --clean --noconfirm $specPath

if ($SkipInstaller) {
    Write-Host 'SkipInstaller flag set; skipping Inno Setup step.' -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $installerScript)) {
    throw "Installer script not found at $installerScript"
}

$innoSetup = $null
try {
    $command = Get-Command iscc.exe -ErrorAction Stop
    $innoSetup = $command.Source
}
catch {
    $defaultPath = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if (Test-Path $defaultPath) {
        $innoSetup = $defaultPath
    }
}

if (-not $innoSetup) {
    Write-Warning 'Inno Setup command-line compiler (ISCC.exe) not found. Install Inno Setup 6 or rerun with -SkipInstaller to build only the portable folder.'
    exit 1
}

Write-Host "Building installer with Inno Setup..." -ForegroundColor Cyan
& $innoSetup $installerScript

Write-Host 'Windows installer build completed.' -ForegroundColor Green
