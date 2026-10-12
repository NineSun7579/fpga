$Host.UI.RawUI.WindowTitle = 'build04 rebuild03 / MAP / PNR 实际日志'
$root = 'C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\build04_constraint_load_fix01\rebuild03'
Write-Host '隔离重建：源码741字节一致；1280 unique和60site硬断言；不bit、不远端。' -ForegroundColor Cyan
$seen = @{}
while ($true) {
    foreach ($file in Get-ChildItem $root -Filter '*.log' -ErrorAction SilentlyContinue) {
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
