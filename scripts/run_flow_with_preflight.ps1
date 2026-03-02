param(
  [Parameter(Mandatory=$true)][string]$Prompt,
  [Parameter(Mandatory=$true)][string]$Out,
  [int]$Retries = 3
)

$py = "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe"
$skillDir = "C:\Users\DELL\.openclaw\workspace\agents\sompro\skills\gemini-video-download\scripts"
$preflight = Join-Path $skillDir "preflight_cdp.py"
$runner = Join-Path $skillDir "flow_click_download.py"

Write-Output "ACK: wrapper started"

& $py $preflight
if ($LASTEXITCODE -ne 0) {
  Write-Output "RESULT: failed"
  Write-Output "ERROR_CODE=E_PREFLIGHT_BLOCKED"
  exit 2
}

Write-Output "PROGRESS: preflight passed, running flow"
$relay = "C:\Users\DELL\.openclaw\workspace\agents\sompro\scripts\heartbeat_relay_runner.py"
& $py $relay --interval 30 -- $py $runner --prompt $Prompt --out $Out --retries $Retries
exit $LASTEXITCODE
