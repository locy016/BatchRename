$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$executable = Join-Path $projectRoot 'src-tauri/target/release/batch-rename.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw "Release executable not found: $executable" }
$before = @(Get-Process batch-rename -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$process = Start-Process -FilePath $executable -PassThru -WindowStyle Hidden
try {
  $deadline = (Get-Date).AddSeconds(15)
  do { Start-Sleep -Milliseconds 250; $process.Refresh() } while (-not $process.HasExited -and $process.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
  if ($process.HasExited) { throw "Application exited early: $($process.ExitCode)" }
  if ($process.MainWindowHandle -eq 0) { throw 'Timed out waiting for the main window.' }
  $file = Get-Item -LiteralPath $executable
  $hash = Get-FileHash -LiteralPath $executable -Algorithm SHA256
  [pscustomobject]@{ Path=$file.FullName; Size=$file.Length; Sha256=$hash.Hash; StartedPid=$process.Id; WindowHandle=$process.MainWindowHandle }
} finally {
  $after = @(Get-Process batch-rename -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $before })
  foreach ($created in $after) { Stop-Process -Id $created.Id -Force -ErrorAction SilentlyContinue }
}
