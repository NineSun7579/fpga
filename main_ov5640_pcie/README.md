# main OV5640→PCIe

本目录承载 `codex/main-ov5640-pcie` 的独立产品实现。当前只包含 M1-A：板级无关的
OV5640 DVP 8-bit 到 RGB565 像素采集切片和自检行为 TB，不依赖 `parallel_driver`。

## 当前文件

- `rtl/ov5640_dvp_rgb565_capture.sv`：`cam_pclk` 域字节拼接、像素坐标和帧/行事件。
- `tb/tb_ov5640_dvp_rgb565_capture.sv`：两行三像素正向场景与半字节负向场景。
- `docs/MAIN_OV5640_PCIE_CAPTURE_CONTRACT.md`：模块接口和验证合同。

## 运行

```powershell
.\scripts\run_m1a.ps1 -SimulatorExecPath '<questa-bin-dir>'
```

运行态只写入 `main_ov5640_pcie/build/`。`vsim.exe`、`vlog.exe` 和许可证配置由本机
环境提供，不写入仓库。当前切片不生成 PDS/IP/位流，也不证明 SCCB、板级电气时序、
DDR3 或 PCIe 集成。
