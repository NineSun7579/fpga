$ErrorActionPreference = 'Stop'

$pds = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^pds' }
if ($pds) {
    throw 'PDS GUI is running. Close PDS before starting the standalone JTAG programmer.'
}

Get-Process cdt_cfg,cdt_js -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

$bin = 'C:\pango\PDS_2022.2-SP6.4\bin'
$port = 65465
$server = $null
$cfg = $null
$outFile = Join-Path $env:TEMP 'pango_cdt_cfg.out.log'
$errFile = Join-Path $env:TEMP 'pango_cdt_cfg.err.log'
Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue
try {
    $server = Start-Process -FilePath "$bin\cdt_js.exe" `
        -ArgumentList '-port', $port -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 4

    # Keep the configuration window alive while the cable programs the FPGA.
    # Close it only after the tool has reported the completed program command.
    $cfg = Start-Process -FilePath "$bin\cdt_cfg.exe" `
        -ArgumentList '-ip','127.0.0.1','-port',$port,'-file','C:\Users\NineSun\Desktop\ov56401\project\flash_jtag.tcl' `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru

    $deadline = (Get-Date).AddMinutes(5)
    $programDone = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $text = if (Test-Path -LiteralPath $outFile) {
            Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue
        } else { '' }
        if ($text -match 'The Progress:.*100%.*The done bit is 1' -or
            $text -match 'The done bit is 1' -and
            $text -match 'COMMAND\[Program\] execute successfully|cfg_program .*successfully') {
            $programDone = $true
            break
        }
        if ($cfg.HasExited) { break }
    }

    if (-not $programDone) {
        $detail = if (Test-Path -LiteralPath $outFile) { Get-Content -LiteralPath $outFile -Raw } else { '' }
        throw "cdt_cfg did not complete programming. $detail"
    }

    Write-Host '100% / done bit / Program successfully detected.'
    Write-Host 'Waiting 10 seconds for the programmer window and cable state to settle.'
    Start-Sleep -Seconds 10
    Write-Host 'Closing the CDT programming window now.'
    Stop-Process -Id $cfg.Id -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $cfg.Id -Timeout 3 -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Write-Host 'Programming window closed; burn completed successfully.'
}
finally {
    if ($cfg -and -not $cfg.HasExited) {
        Stop-Process -Id $cfg.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process cdt_cfg,cdt_js -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    if ($server) {
        Wait-Process -Id $server.Id -Timeout 3 -ErrorAction SilentlyContinue
    }
}

Write-Host 'JTAG programming flow finished; cdt_js was stopped.'
