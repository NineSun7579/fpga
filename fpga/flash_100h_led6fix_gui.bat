@echo off
echo ============================================
echo 100H LED6修复版烧录
echo ============================================
echo.
echo 比特流: project_build\generate_bitstream\top.sbit
echo 修复内容: SFP TX idle改为标准GE /I2/ 有序集
echo.
echo 烧录前检查:
echo   1. 100H板已连接JTAG (USB Blaster)
echo   2. 100H板已上电
echo   3. 确认LED心跳正常
echo.
pause
echo.
echo 启动PDS GUI烧录工具...
echo.
start "" "C:\pango\PDS_2022.2-SP6.4\bin\cdt_cfg.exe"
echo.
echo GUI打开后操作:
echo   1. Connect (连接JTAG)
echo   2. Scan Chain (扫描器件，应显示PG2L100H)
echo   3. Browse选择: %~dp0project_build\generate_bitstream\top.sbit
echo   4. Program Device (烧录到SRAM)
echo   5. 验证功能正常后: Flash Erase + Flash Program (烧录到Flash)
echo.
echo 验证清单:
echo   - LED4(A3)亮 = TX有光
echo   - 光纤对接50K板后，50K LED6(A5)应点亮
echo   - RK3568 camview C5/C6通道有画面
echo.
pause
