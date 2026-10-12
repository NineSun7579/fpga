$Host.UI.RawUI.WindowTitle = 'build04_constraint_load_fix01 实际构建日志（compile/syn/map，无PNR）'
$root = 'C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\build04_constraint_load_fix01'
Write-Host '真实日志窗口：编程已DONE；只编译、综合、映射和原生CDB核验。' -ForegroundColor Cyan
$seen = @{}
while ($true) {
    foreach ($file in Get-ChildItem $root -Filter '*.log') {
        $lines = @(Get-Content -LiteralPath $file.FullName)
        $prior = 0
        if ($seen.ContainsKey($file.FullName)) { $prior = $seen[$file.FullName] }
        if ($lines.Count -gt $prior) {
            Write-Host ('【实际工具】' + $file.Name) -ForegroundColor Yellow
            $lines | Select-Object -Skip $prior | ForEach-Object { Write-Host $_ }
            $seen[$file.FullName] = $lines.Count
        }
    }
    if (Test-Path (Join-Path $root 'actual_review_handoff.json')) { Write-Host '原生核验结束，交接文件已生成。'; break }
    Start-Sleep -Seconds 3
}
Read-Host '按回车关闭日志窗口'
