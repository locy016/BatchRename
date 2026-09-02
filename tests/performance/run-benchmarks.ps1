$ErrorActionPreference='Stop';$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
foreach($count in 1000,10000){cargo run --quiet --manifest-path (Join-Path $root 'src-tauri/Cargo.toml') --example benchmark_workflow -- $count}
