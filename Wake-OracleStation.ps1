param(
  [string]$BaseUrl = "http://127.0.0.1:7781"
)

Write-Host ""
Write-Host "ORACLE POWERSHELL STATION" -ForegroundColor Cyan
Write-Host "Local endpoint: $BaseUrl" -ForegroundColor DarkCyan
Write-Host "Type /exit to close." -ForegroundColor DarkGray
Write-Host ""

function Send-OracleMessage {
  param([string]$Message)

  $payloads = @(
    @{ message = $Message },
    @{ text = $Message },
    @{ prompt = $Message },
    @{ input = $Message },
    @{ content = $Message }
  )

  foreach ($payload in $payloads) {
    try {
      $json = $payload | ConvertTo-Json -Depth 10
      $response = Invoke-RestMethod "$BaseUrl/chat" -Method Post -ContentType "application/json" -Body $json -TimeoutSec 60
      return $response
    } catch {
      $lastError = $_.Exception.Message
    }
  }

  return @{
    error = "No accepted /chat payload shape found."
    last_error = $lastError
  }
}

try {
  $status = Invoke-RestMethod "$BaseUrl/api/status" -TimeoutSec 10
  Write-Host "Status: connected" -ForegroundColor Green
} catch {
  Write-Host "Status: could not reach ORACLE at $BaseUrl" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor DarkRed
}

while ($true) {
  Write-Host ""
  $msg = Read-Host "Noah.Physical"

  if ($msg -eq "/exit") {
    Write-Host "Station closed." -ForegroundColor DarkGray
    break
  }

  if ([string]::IsNullOrWhiteSpace($msg)) {
    continue
  }

  Write-Host ""
  Write-Host "ORACLE" -ForegroundColor Magenta

  $reply = Send-OracleMessage -Message $msg

  if ($reply -is [string]) {
    Write-Host $reply
  } else {
    $reply | ConvertTo-Json -Depth 20
  }
}
