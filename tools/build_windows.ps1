Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$specPath = Join-Path $repoRoot "HoroscopeApp.spec"

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found at $venvPython"
}

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec file not found at $specPath"
}

Push-Location $repoRoot
try {
    & $venvPython -m PyInstaller --clean --noconfirm $specPath
    Write-Host ""
    Write-Host "Build completed."
    Write-Host "Executable folder: $(Join-Path $repoRoot 'dist\HoroscopeApp')"
}
finally {
    Pop-Location
}
