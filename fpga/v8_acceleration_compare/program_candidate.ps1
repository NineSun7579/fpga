param(
    [Parameter(Mandatory=$true)][string]$Bitstream,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory
)
$ErrorActionPreference = 'Stop'
$bitPath = (Resolve-Path $Bitstream).Path
if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid expected bitstream SHA256' }
if ((Get-FileHash $bitPath -Algorithm SHA256).Hash -ne $ExpectedSha256) {
    throw 'Bitstream identity differs from reviewed build'
}
if (Get-Process pds,pds_shell -ErrorAction SilentlyContinue) { throw 'PDS is running' }
$binPath = 'C:\pango\PDS_2022.2-SP6.4\bin'
New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null
$evidencePath = (Resolve-Path $EvidenceDirectory).Path
$tclPath = Join-Path $evidencePath 'jtag.tcl'
$logPath = Join-Path $evidencePath 'jtag.log'
$errorPath = Join-Path $evidencePath 'jtag.err.log'
$bitForTcl = $bitPath.Replace('\','/')
@('cfg_scan_chain', 'cfg_set_cable_property -index 0 -freq 1MHz',
  "cfg_assign_file -file {$bitForTcl} -device_index 0", 'cfg_program -device_index 0') |
    Set-Content -Path $tclPath -Encoding ascii
$serverProcess = Start-Process "$binPath\cdt_js.exe" -ArgumentList '-port','65470' -PassThru -WindowStyle Hidden
$programProcess = $null
try {
    Start-Sleep -Seconds 4
    $programProcess = Start-Process "$binPath\cdt_cfg.exe" -ArgumentList '-ip','127.0.0.1','-port','65470','-file',('"'+$tclPath+'"') -PassThru -RedirectStandardOutput $logPath -RedirectStandardError $errorPath
    $deadline = (Get-Date).AddMinutes(10)
    $complete = $false
    while ((Get-Date) -lt $deadline) {
        $text = Get-Content $logPath -Raw -ErrorAction SilentlyContinue
        $complete = $text -match 'The done bit is 1' -and $text -match 'COMMAND\[Program\] execute successfully'
        if ($complete -or $programProcess.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $complete) { throw 'No verified JTAG completion marker' }
    $text = Get-Content $logPath -Raw
    if ($text -match 'execute failed|Error:|(?m)^E:') { throw 'Programmer reported failure' }
    if ((Get-FileHash $bitPath -Algorithm SHA256).Hash -ne $ExpectedSha256) { throw 'Bitstream changed during programming' }
    Write-Output $text
} finally {
    if ($programProcess -and -not $programProcess.HasExited) { Stop-Process -Id $programProcess.Id -Force }
    if (-not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id -Force }
}
