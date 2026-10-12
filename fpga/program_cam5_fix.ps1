param([switch]$Persistent)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$bin = 'C:\pango\PDS_2022.2-SP6.4\bin'
$bit = Join-Path $root 'project_cam5_fix_build02\generate_bitstream\top.sbit'
if (-not (Test-Path $bit)) { throw 'Verified build bitstream is missing' }
if (Get-Process pds,pds_shell -ErrorAction SilentlyContinue) { throw 'PDS is running' }
$stem = if ($Persistent) { 'cam5_spi' } else { 'cam5_jtag' }
$script = Join-Path $root "$stem.tcl"
$bitTcl = $bit.Replace('\','/')
$commands = @('cfg_scan_chain', 'cfg_set_cable_property -index 0 -freq 1MHz')
if ($Persistent) {
    $commands += @('cfg_jtag_flash_scan_device -device_index 0',
        "cfg_jtag_flash_assign_file -file $bitTcl -device_index 0",
        'cfg_jtag_flash_erase -device_index 0',
        'cfg_jtag_flash_program -device_index 0',
        'cfg_jtag_flash_verify -device_index 0')
} else {
    $commands += @("cfg_assign_file -file $bitTcl -device_index 0", 'cfg_program -device_index 0')
}
$commands | Set-Content -Path $script -Encoding ascii
$server = Start-Process "$bin\cdt_js.exe" -ArgumentList '-port','65470' -PassThru -WindowStyle Hidden
$cfg = $null
try {
    Start-Sleep -Seconds 4
    $cfg = Start-Process "$bin\cdt_cfg.exe" -ArgumentList '-ip','127.0.0.1','-port','65470','-file',$script -PassThru -RedirectStandardOutput "$root\$stem.log" -RedirectStandardError "$root\$stem.err.log"
    $deadline = (Get-Date).AddMinutes(10)
    $done = $false
    while ((Get-Date) -lt $deadline) {
        $text = Get-Content "$root\$stem.log" -Raw -ErrorAction SilentlyContinue
        if ($Persistent) {
            $done = $text -match 'Executing : cfg_jtag_flash_verify -device_index 0 successfully'
        } else {
            $done = $text -match 'The done bit is 1' -and $text -match 'COMMAND\[Program\] execute successfully'
        }
        if ($done -or $cfg.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $done) { throw 'Programmer did not report verified completion' }
    $log = Get-Content "$root\$stem.log" -Raw
    if ($log -match 'execute failed|Error:|^E:') { throw 'Programmer reports failure' }
    Write-Output $log
} finally {
    if ($cfg -and -not $cfg.HasExited) { Stop-Process -Id $cfg.Id -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}
