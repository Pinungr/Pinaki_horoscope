Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$specPath = Join-Path $repoRoot "HoroscopeApp.spec"
$ephemerisSource = Join-Path $repoRoot "app\data\ephemeris"
$distEphemerisDir = Join-Path $repoRoot "dist\HoroscopeApp\ephemeris"

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found at $venvPython"
}

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec file not found at $specPath"
}

Push-Location $repoRoot
try {
    & $venvPython -m PyInstaller --clean --noconfirm $specPath
    New-Item -ItemType Directory -Force -Path $distEphemerisDir | Out-Null
    if (Test-Path $ephemerisSource) {
        Copy-Item -Path (Join-Path $ephemerisSource "*") -Destination $distEphemerisDir -Recurse -Force
    }
    Write-Host ""
    Write-Host "Build completed."
    Write-Host "Executable folder: $(Join-Path $repoRoot 'dist\HoroscopeApp')"
}
finally {
    Pop-Location
}
