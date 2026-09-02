$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
  npm run test
  if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
  cargo test --manifest-path src-tauri/Cargo.toml
  if ($LASTEXITCODE -ne 0) { throw 'Rust tests failed.' }
  python -m pytest tests/compat tests/release -q
  if ($LASTEXITCODE -ne 0) { throw 'Compatibility tests failed.' }
  npm run tauri build
  if ($LASTEXITCODE -ne 0) { throw 'Windows release build failed.' }
} finally { Pop-Location }
