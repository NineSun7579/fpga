param(
    [Parameter(Mandatory=$true)][string]$Sbit,
    [string]$TclOut = 'C:\Users\NineSun\AppData\Local\Temp\opencode\flash_any.tcl',
    [string]$LogPrefix = 'flash_any'
)
$ErrorActionPreference = 'Stop'

$pds = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^pds' }
if ($pds) { throw 'PDS is running. Close PDS before starting the standalone JTAG programmer.' }

Get-Process cdt_cfg, cdt_js -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$proj  = 'C:\Users\NineSun\Desktop\ov56401\project'
$bin   = 'C:\pango\PDS_2022.2-SP6.4\bin'
$port  = 65470
if (-not (Test-Path -LiteralPath $Sbit)) { throw "bitstream not found: $Sbit" }
# normalize to forward slashes for the Tcl file
$sbitT = $Sbit -replace '\\','/'
"cfg_scan_chain`r`ncfg_assign_file -file $sbitT -device_index 0`r`ncfg_program -device_index 0" |
    Set-Content -LiteralPath $TclOut -Encoding ascii

$outFile = Join-Path $proj "$LogPrefix.out.log"
$errFile = Join-Path $proj "$LogPrefix.err.log"
Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue

$server = $null; $cfg = $null; $programDone = $false
try {
    $server = Start-Process -FilePath "$bin\cdt_js.exe" -ArgumentList '-port', $port -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 4
    $cfg = Start-Process -FilePath "$bin\cdt_cfg.exe" `
        -ArgumentList '-ip','127.0.0.1','-port',$port,'-file',$TclOut `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $text = if (Test-Path -LiteralPath $outFile) { Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue } else { '' }
        if ($text -match 'The done bit is 1' -and $text -match 'COMMAND\[Program\] execute successfully') { $programDone = $true; break }
        $cfg.Refresh(); if ($cfg.HasExited) { break }
    }
} finally {
    if ($cfg -and -not $cfg.HasExited) { Stop-Process -Id $cfg.Id -Force -ErrorAction SilentlyContinue }
    Get-Process cdt_js -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if ($server) { Wait-Process -Id $server.Id -Timeout 3 -ErrorAction SilentlyContinue }
}

$text = if (Test-Path -LiteralPath $outFile) { Get-Content -LiteralPath $outFile -Raw } else { '' }
if ($programDone) { Write-Host "FLASH_RESULT: SUCCESS ($Sbit)" }
else { Write-Host 'FLASH_RESULT: FAILED'; Write-Host $text; exit 1 }
