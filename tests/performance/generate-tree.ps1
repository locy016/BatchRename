param([Parameter(Mandatory=$true)][string]$Root,[int]$Count=1000)
$resolved=[IO.Path]::GetFullPath($Root);New-Item -ItemType Directory -Force -Path $resolved|Out-Null
for($i=0;$i-lt $Count;$i++){[IO.File]::WriteAllText((Join-Path $resolved ("项目旧版_{0:D6}.txt" -f $i)),"")}
