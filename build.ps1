$ErrorActionPreference = "Stop"

Write-Host "[1/3] Checking build tools..." -ForegroundColor Cyan
python -c "import pytest, PyInstaller; print('pytest', pytest.__version__, '| PyInstaller', PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Missing build dependencies. Run: python -m pip install -r requirements-dev.txt"
}

Write-Host "[2/3] Running automated tests..." -ForegroundColor Cyan
python -m pytest -v
if ($LASTEXITCODE -ne 0) {
    throw "Tests failed. Build stopped."
}

Write-Host "[3/3] Building the single-file application..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm BatchRename.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$artifactPath = Join-Path $PSScriptRoot "dist\BatchRename.exe"
if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
    throw "Build finished without producing dist\BatchRename.exe."
}

$artifact = Get-Item -LiteralPath $artifactPath
Write-Host ("Build complete: {0} ({1:N2} MB)" -f $artifact.FullName, ($artifact.Length / 1MB)) -ForegroundColor Green
