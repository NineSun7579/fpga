$Host.UI.RawUI.WindowTitle = 'build04 fresh MAP / PNR 实际日志'
$root = 'C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\build04_constraint_load_fix01'
Write-Host '新综合已完成；串行新MAP、独立PNR、原生时序核验。失败日志保留，不生成bit。' -ForegroundColor Cyan
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
    Start-Sleep -Seconds 3
}
