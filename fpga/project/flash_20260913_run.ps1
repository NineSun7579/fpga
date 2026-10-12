$ErrorActionPreference = 'Stop'

# Guard: no PDS GUI / other cable owners running.
$pds = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^pds' }
if ($pds) {
    throw 'PDS is running. Close PDS before starting the standalone JTAG programmer.'
}

Get-Process cdt_cfg, cdt_js -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

$bin   = 'C:\pango\PDS_2022.2-SP6.4\bin'
$port  = 65465
$tcl   = 'C:\Users\NineSun\Desktop\ov56401\project\flash_2026-09-13_final.tcl'
$sbit  = 'C:\Users\NineSun\Desktop\ov56401\project\bitstream_2026-09-13_final\top.sbit'
$outFile = 'C:\Users\NineSun\Desktop\ov56401\project\flash_20260913.out.log'
$errFile = 'C:\Users\NineSun\Desktop\ov56401\project\flash_20260913.err.log'

if (-not (Test-Path -LiteralPath $sbit)) { throw "bitstream not found: $sbit" }
Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue

$server = $null
$cfg = $null
$programDone = $false
try {
    $server = Start-Process -FilePath "$bin\cdt_js.exe" `
        -ArgumentList '-port', $port -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 4

    $cfg = Start-Process -FilePath "$bin\cdt_cfg.exe" `
        -ArgumentList '-ip','127.0.0.1','-port',$port,'-file',$tcl `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru

    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $text = if (Test-Path -LiteralPath $outFile) {
            Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue
        } else { '' }
        if ($text -match 'The done bit is 1' -and
            $text -match 'COMMAND\[Program\] execute successfully') {
            $programDone = $true
            break
        }
        $cfg.Refresh()
        if ($cfg.HasExited) { break }
    }
}
finally {
    if ($cfg -and -not $cfg.HasExited) {
        Stop-Process -Id $cfg.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process cdt_js -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    if ($server) { Wait-Process -Id $server.Id -Timeout 3 -ErrorAction SilentlyContinue }
}

$text = if (Test-Path -LiteralPath $outFile) { Get-Content -LiteralPath $outFile -Raw } else { '' }
if ($programDone) {
    Write-Host 'FLASH_RESULT: SUCCESS'
    Write-Host '100% / done bit is 1 / Program execute successfully'
} else {
    Write-Host 'FLASH_RESULT: FAILED'
    Write-Host $text
    exit 1
}
