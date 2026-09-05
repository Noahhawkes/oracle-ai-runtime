<#
  ORACLE.ps1 - ORACLE Operator Home launcher (v1)

  One face. One button. One operator home. This launcher exists so Noah never
  has to remember 7777 / 7778 / 7781 again, and is never silently dropped onto a
  stale interface.

  What it does:
    1. Detects the four known local ports (7777 legacy, 7778 preview, 7781
       canonical runtime, 11434 Ollama) and labels each current / stale / preview.
    2. Generates a fresh ui/operator_home.html with that status baked in.
    3. Opens Operator Home (unless -Report). Operator Home links to the CURRENT
       runtime (7781), never silently to the stale 7777 copy.
    4. If the canonical runtime is down, says exactly what to run - it does not
       auto-spawn the elevated server (that is Noah's action) unless -Start.

  Boundary laws (see docs/oracle_desktop_boundary_laws.md):
    REFRESH_MUST_NOT_DESTROY_THREAD
    LOCAL_CHAT_STATE != DURABLE_MEMORY
    DESKTOP_APP_EXPECTATION != BROWSER_TAB_EXPERIMENT
    NOAH_SHOULD_NOT_HAVE_TO_REMEMBER_PORTS

  Usage:
    .\ORACLE.ps1            # detect, generate Operator Home, open it
    .\ORACLE.ps1 -Report    # detect + generate, do NOT open a browser (testable)
    .\ORACLE.ps1 -Start     # if 7781 is down, launch oracle_desktop.bat first
#>
[CmdletBinding()]
param(
  [switch]$Report,   # generate Operator Home but do not open a browser
  [switch]$Start     # if canonical runtime is down, start it via oracle_desktop.bat
)

# Probes carry their own try/catch; don't let incidental non-terminating cmdlet
# noise abort the launcher or report a false failure to the .bat / shortcut.
$ErrorActionPreference = 'Continue'
$CanonicalPort = 7781

# ── Repo-root resolution + HARD-FAIL guard (BUG_001 / BUG_003) ────────────────
# When this script is PASTED into a PowerShell prompt instead of run as a saved
# file, $PSScriptRoot and $MyInvocation.MyCommand.Path are empty, so the old
# code resolved $RepoRoot to the current directory (e.g. C:\WINDOWS\system32).
# That made manifest counts 0 and tried to write Operator Home into system32.
# Resolve from the script file when possible, fall back to the known repo, and
# REFUSE to run unless the root actually looks like the ORACLE repo.
$RepoRoot = $null
if ($PSScriptRoot) { $RepoRoot = $PSScriptRoot }
elseif ($MyInvocation.MyCommand.Path) { $RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $RepoRoot -or -not (Test-Path (Join-Path $RepoRoot 'oracle_server.py'))) {
  if (Test-Path 'C:\Oracle\ORACLE.AI-runtime\oracle_server.py') {
    $RepoRoot = 'C:\Oracle\ORACLE.AI-runtime'
  }
}

# Markers that prove we are at the real repo root, not system32 or anywhere else.
$RequiredMarkers = @('oracle_server.py', 'core\runtime_config.py', 'ui')
$missing = @()
foreach ($m in $RequiredMarkers) {
  if (-not $RepoRoot -or -not (Test-Path (Join-Path $RepoRoot $m))) { $missing += $m }
}
if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "ORACLE LAUNCH REFUSED - not running from the repo root." -ForegroundColor Red
  Write-Host ("  Resolved root: {0}" -f ($(if ($RepoRoot) { $RepoRoot } else { '(empty)' }))) -ForegroundColor DarkRed
  Write-Host ("  Missing markers: {0}" -f ($missing -join ', ')) -ForegroundColor DarkRed
  Write-Host "  Do NOT paste this script into a prompt. Run the saved file:" -ForegroundColor Yellow
  Write-Host "    C:\Oracle\ORACLE.AI-runtime\ORACLE_HOME.bat" -ForegroundColor Yellow
  Write-Host "    (or)  powershell -ExecutionPolicy Bypass -File C:\Oracle\ORACLE.AI-runtime\ORACLE.ps1" -ForegroundColor Yellow
  exit 3
}

# Port -> meaning. Single source of truth for what each local port IS.
$PortSpec = @(
  @{ Port = 7777;  Name = 'Legacy UI';        Role = 'stale'   ; Probe = '/api/mode' }
  @{ Port = 7778;  Name = 'Preview/Dev';      Role = 'preview' ; Probe = '/api/mode' }
  @{ Port = 7781;  Name = 'ORACLE Runtime';   Role = 'current' ; Probe = '/api/mode' }
  @{ Port = 11434; Name = 'Ollama models';    Role = 'service' ; Probe = '/api/tags' }
)

function Html-Encode {
  param([string]$s)
  if (-not $s) { return '' }
  return ($s -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' -replace '"','&quot;')
}

function Test-Port {
  param([int]$Port)
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(700)
    if ($ok -and $c.Connected) { $c.Close(); return $true }
    $c.Close(); return $false
  } catch { return $false }
}

function Test-Http {
  # Layer-7 check (BUG_005): a TCP handshake is NOT proof the app answers.
  # Returns $true only on a real HTTP response. -UseBasicParsing for PS 5.1 (BUG_004).
  param([int]$Port, [string]$Path = '/api/mode')
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port$Path" -UseBasicParsing -TimeoutSec 3
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch {
    # An HTTP error status still proves the app answered at layer 7.
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { return $true }
    return $false
  }
}

function Get-ProcOwner {
  param([int]$Port)
  try {
    $line = (netstat -ano | Select-String ":$Port\s" | Select-String 'LISTENING' | Select-Object -First 1)
    if (-not $line) { return $null }
    $procId = ($line.ToString() -split '\s+')[-1]
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
    if ($p) { return @{ Pid = $procId; Cmd = $p.CommandLine } }
    return @{ Pid = $procId; Cmd = $null }
  } catch { return $null }
}

Write-Host ""
Write-Host "ORACLE Operator Home - detecting runtimes..." -ForegroundColor Cyan

$now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$rows = @()
$runtimeUp = $false

foreach ($spec in $PortSpec) {
  $up = Test-Port -Port $spec.Port          # layer-4: is the port open?
  $owner = $null
  $note = ''
  if ($up) {
    $owner = Get-ProcOwner -Port $spec.Port
    # Layer-7: does the app actually answer? Only then is a runtime "alive".
    $http = Test-Http -Port $spec.Port -Path $spec.Probe
    if (-not $http) {
      $note = 'port open but app NOT responding (layer-4 only)'
      $up = $false   # do not present a half-dead port as online
    }
    if ($spec.Port -eq $CanonicalPort -and $http) { $runtimeUp = $true }
    # Flag the known stale Google Drive copy explicitly.
    if ($spec.Port -eq 7777 -and $owner -and $owner.Cmd -and $owner.Cmd -match 'G:\\My Drive') {
      $note = 'STALE Google Drive copy - NOT the governed runtime'
    }
  }
  $rows += [pscustomobject]@{
    Port  = $spec.Port
    Name  = $spec.Name
    Role  = $spec.Role
    Up    = $up
    Pid   = if ($owner) { $owner.Pid } else { '' }
    Cmd   = if ($owner -and $owner.Cmd) { $owner.Cmd } else { '' }
    Note  = $note
  }
  $state = if ($up) { 'UP  ' } else { 'DOWN' }
  $color = if ($up) { 'Green' } else { 'DarkGray' }
  if ($spec.Port -eq 7777 -and $up) { $color = 'Yellow' }
  Write-Host ("  [{0}] :{1,-5} {2,-16} {3}" -f $state, $spec.Port, $spec.Name, $note) -ForegroundColor $color
}

# Optionally start the canonical runtime if it is down.
if (-not $runtimeUp -and $Start) {
  $bat = Join-Path $RepoRoot 'oracle_desktop.bat'
  if (Test-Path $bat) {
    Write-Host "  Canonical runtime down - launching oracle_desktop.bat ..." -ForegroundColor Yellow
    Start-Process -FilePath $bat -WorkingDirectory $RepoRoot -WindowStyle Hidden
    for ($i = 0; $i -lt 15 -and -not $runtimeUp; $i++) {
      Start-Sleep -Seconds 1
      $runtimeUp = Test-Port -Port $CanonicalPort
    }
  } else {
    Write-Host "  Cannot start: $bat not found." -ForegroundColor Red
  }
}

# Source-map status (real: file existence + line counts).
function Count-Lines { param([string]$Rel)
  $p = Join-Path $RepoRoot $Rel
  if (Test-Path $p) { return (Get-Content $p | Where-Object { $_.Trim() } | Measure-Object).Count }
  return -1
}
$mdCount = Count-Lines 'research_canon\miricledrive_source_manifest.jsonl'
$rrCount = Count-Lines 'research_canon\rendered_reality_source_family.jsonl'

# Build the HTML rows.
$htmlRows = ($rows | ForEach-Object {
  $stateTxt = if ($_.Up) { 'ONLINE' } else { 'offline' }
  $cls = if ($_.Up) { 'up' } else { 'down' }
  if ($_.Port -eq 7777 -and $_.Up) { $cls = 'stale' }
  if ($_.Port -eq $CanonicalPort -and $_.Up) { $cls = 'current' }
  $noteTxt = if ($_.Note) { $_.Note } elseif ($_.Cmd) { Html-Encode $_.Cmd } else { '' }
  "<tr class='$cls'><td>:$($_.Port)</td><td>$($_.Name)</td><td>$($_.Role)</td><td class='st'>$stateTxt</td><td>$($_.Pid)</td><td class='note'>$noteTxt</td></tr>"
}) -join "`n"

$runtimeBanner = if ($runtimeUp) {
  "<a class='btn primary' href='http://127.0.0.1:$CanonicalPort/' target='_blank'>Open ORACLE Runtime (:$CanonicalPort)</a>"
} else {
  "<div class='alert'>Canonical runtime (:$CanonicalPort) is <b>DOWN</b>. Start it from <code>$RepoRoot</code>:<br><code>oracle_desktop.bat</code>&nbsp; or &nbsp;<code>python oracle_server.py --port $CanonicalPort</code><br>(The web server runs elevated; restarting it is Noah.Physical's action.)</div>"
}
$staleWarn = ''
if (($rows | Where-Object { $_.Port -eq 7777 -and $_.Up })) {
  $staleWarn = "<div class='alert stale'>A process is answering on <b>:7777</b>. This is the legacy/stale interface (historically the Google Drive mirror copy). Do <b>not</b> treat it as ORACLE. Use :$CanonicalPort.</div>"
}

$html = @"
<!doctype html><html><head><meta charset='utf-8'><title>ORACLE Operator Home</title>
<style>
 body{background:#0b0f14;color:#d7e0ea;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:28px}
 h1{font-size:20px;margin:0 0 2px} .sub{color:#7c8a9a;margin:0 0 18px}
 table{border-collapse:collapse;width:100%;margin:10px 0 18px} th,td{padding:7px 10px;text-align:left;border-bottom:1px solid #1c2630}
 th{color:#7c8a9a;font-weight:600;font-size:12px;text-transform:uppercase}
 tr.current .st{color:#46d39a;font-weight:700} tr.up .st{color:#46d39a} tr.down .st{color:#5b6a78} tr.down{opacity:.55}
 tr.stale .st{color:#e6b450;font-weight:700} .note{color:#8a97a6;font-size:12px;max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .btn{display:inline-block;padding:10px 16px;border-radius:8px;text-decoration:none;margin:4px 8px 4px 0;border:1px solid #2a3744;color:#d7e0ea}
 .btn.primary{background:#1f6feb;border-color:#1f6feb;color:#fff} .alert{background:#15202b;border:1px solid #2a3744;border-radius:8px;padding:12px 14px;margin:10px 0}
 .alert.stale{border-color:#5a4a1f;background:#1f1a10;color:#e6b450} code{background:#0f1620;padding:1px 6px;border-radius:4px;color:#9fd0ff}
 .cards{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 18px} .card{background:#11181f;border:1px solid #1c2630;border-radius:10px;padding:12px 16px;min-width:170px}
 .card b{display:block;font-size:20px;color:#fff} .foot{color:#5b6a78;font-size:12px;margin-top:20px}
</style></head><body>
<h1>ORACLE Operator Home</h1>
<p class='sub'>One face. One button. Generated $now &middot; canonical runtime :$CanonicalPort</p>
$runtimeBanner
$staleWarn
<h3>Runtimes</h3>
<table><tr><th>Port</th><th>Component</th><th>Role</th><th>State</th><th>PID</th><th>Owner / note</th></tr>
$htmlRows
</table>
<div class='cards'>
 <div class='card'>Pending approvals<b><a class='st' href='http://127.0.0.1:$CanonicalPort/' target='_blank' style='color:#9fd0ff'>open /pending</a></b><span class='note'>live - via runtime</span></div>
 <div class='card'>MiricleDrive sources<b>$mdCount</b><span class='note'>research_canon/miricledrive_source_manifest.jsonl</span></div>
 <div class='card'>Rendered Reality sources<b>$rrCount</b><span class='note'>rendered_reality_source_family.jsonl</span></div>
</div>
<a class='btn' href='http://127.0.0.1:$CanonicalPort/api/history' target='_blank'>Current thread (/api/history)</a>
<a class='btn' href='http://127.0.0.1:$CanonicalPort/health' target='_blank'>Healthcheck (/health)</a>
<p class='foot'>Threads are durable: every turn is written to Memory/oracle_memory.db and replayed on refresh via /api/history. REFRESH_MUST_NOT_DESTROY_THREAD. This page is a generated snapshot - re-run ORACLE to refresh status.</p>
</body></html>
"@

$outPath = Join-Path $RepoRoot 'ui\operator_home.html'
# Honest write reporting (BUG_002): only claim success if the file actually
# wrote AND now exists. A failed write must NEVER print "committed".
$wrote = $false
try {
  Set-Content -Path $outPath -Value $html -Encoding UTF8 -ErrorAction Stop
  $wrote = (Test-Path $outPath) -and ((Get-Item $outPath).Length -gt 0)
} catch {
  Write-Host ""
  Write-Host "  Operator Home WRITE FAILED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "  Path attempted: $outPath" -ForegroundColor DarkRed
}
Write-Host ""
if ($wrote) {
  Write-Host "  Operator Home written: $outPath" -ForegroundColor Cyan
  Write-Host ("  MiricleDrive sources: {0} | Rendered Reality sources: {1}" -f $mdCount, $rrCount) -ForegroundColor DarkCyan
} else {
  Write-Host "  Operator Home NOT committed (see error above). Status not snapshotted." -ForegroundColor Red
}

if (-not $Report) {
  if ($runtimeUp) {
    Start-Process "http://127.0.0.1:$CanonicalPort/"
  } elseif ($wrote) {
    Start-Process $outPath
  }
}
Write-Host ""
# Exit non-zero if the snapshot did not commit, so the .bat / shortcut can tell.
if ($wrote) { exit 0 } else { exit 4 }
