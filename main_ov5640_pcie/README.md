# main OV5640→PCIe

本目录承载 `codex/main-ov5640-pcie` 的独立产品实现。当前完成 M1-A 采集和 M2-A
灰度处理两个板级无关切片，不依赖 `parallel_driver`。

## 当前文件

- `rtl/ov5640_dvp_rgb565_capture.sv`：`cam_pclk` 域字节拼接、像素坐标和帧/行事件。
- `rtl/rgb565_grayscale.sv`：RGB565 灰度化，固定一拍处理延迟。
- `rtl/ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的板级无关连接。
- `tb/tb_ov5640_dvp_rgb565_capture.sv`：采集模块两行三像素场景与半字节负向场景。
- `tb/tb_ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的像素、边界和错误自检。
- `docs/MAIN_OV5640_PCIE_CAPTURE_CONTRACT.md`：模块接口和验证合同。
- `docs/MAIN_OV5640_PCIE_PROCESS_CONTRACT.md`：图像处理算法和延迟合同。

## 运行

```powershell
.\scripts\run_m1a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m2a.ps1 -SimulatorExecPath '<questa-bin-dir>'
```

运行态只写入 `main_ov5640_pcie/build/`。`vsim.exe`、`vlog.exe` 和许可证配置由本机
环境提供，不写入仓库。当前切片不生成 PDS/IP/位流，也不证明 SCCB、板级电气时序、
CDC/FIFO、DDR3 或 PCIe 集成。
