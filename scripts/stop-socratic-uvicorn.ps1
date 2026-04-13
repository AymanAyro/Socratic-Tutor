# Stops orphan uvicorn processes for this repo (e.g. left running from Cursor/agent or closed terminals).
# They keep port 8000 busy so a NEW terminal uvicorn never receives traffic - curl still works, logs look "dead".
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$marker = [regex]::Escape($repoRoot.Path)

$killed = @()
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | ForEach-Object {
  $line = $_.CommandLine
  if (-not $line) { return }
  if ($line -notmatch 'uvicorn') { return }
  if ($line -notmatch $marker) { return }
  $id = $_.ProcessId
  Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
  $killed += $id
}

if ($killed.Count -eq 0) {
  Write-Host "No matching Socratic Tutor uvicorn python.exe processes found."
} else {
  Write-Host "Stopped PIDs: $($killed -join ', ')"
}
