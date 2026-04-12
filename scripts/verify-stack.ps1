param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$uri = "$BaseUrl/api/v1/health/ready".TrimEnd("/")

$jsonText = $null
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
  $jsonText = curl.exe -sS --max-time 30 $uri
  if ($LASTEXITCODE -ne 0) {
    Write-Error "Cannot reach $uri - start the API (e.g. uvicorn) and ensure Postgres, Redis, and Chroma are up."
    exit 1
  }
} else {
  try {
    $r = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30
    $jsonText = $r.Content
  } catch {
    Write-Error "Cannot reach $uri - start the API (e.g. uvicorn) and ensure Postgres, Redis, and Chroma are up. $_"
    exit 1
  }
}

try {
  $j = $jsonText | ConvertFrom-Json
} catch {
  Write-Error "Invalid JSON from /ready: $jsonText"
  exit 1
}

$checks = $j.checks
if (-not $checks) {
  Write-Error "Unexpected /ready payload (no checks): $jsonText"
  exit 1
}

$bad = @()
foreach ($k in $checks.PSObject.Properties.Name) {
  if ($checks.$k -ne "ok") {
    $bad += "${k}: $($checks.$k)"
  }
}

if ($bad.Count -gt 0) {
  Write-Error "Readiness degraded: $($bad -join '; ')"
  exit 1
}

Write-Host "OK: postgres, redis, chromadb - $($j.status)"
