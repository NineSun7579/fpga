# main OV5640→PCIe

本目录承载 `codex/main-ov5640-pcie` 的独立产品实现。当前完成 M1-A 采集、M2-A
灰度处理和 M3-A 128-bit 图像字打包三个板级无关切片，不依赖 `parallel_driver`。

## 当前文件

- `rtl/ov5640_dvp_rgb565_capture.sv`：`cam_pclk` 域字节拼接、像素坐标和帧/行事件。
- `rtl/rgb565_grayscale.sv`：RGB565 灰度化，固定一拍处理延迟。
- `rtl/ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的板级无关连接。
- `rtl/rgb565_word_packer.sv`：RGB565 像素到 128-bit 数据字的顺序打包。
- `rtl/ov5640_dvp_rgb565_word_pipeline.sv`：采集、灰度处理和 128-bit 打包连接。
- `tb/tb_ov5640_dvp_rgb565_capture.sv`：采集模块两行三像素场景与半字节负向场景。
- `tb/tb_ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的像素、边界和错误自检。
- `tb/tb_rgb565_word_packer.sv`：完整字、部分行尾字和控制事件自检。
- `tb/tb_ov5640_dvp_rgb565_word_pipeline.sv`：DVP 到 128-bit 图像字集成自检。
- `docs/MAIN_OV5640_PCIE_CAPTURE_CONTRACT.md`：模块接口和验证合同。
- `docs/MAIN_OV5640_PCIE_PROCESS_CONTRACT.md`：图像处理算法和延迟合同。
- `docs/MAIN_OV5640_PCIE_WORD_PACKER_CONTRACT.md`：128-bit 内部数据布局合同。
- `docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`：DDR3/PCIe 适配层职责、转换边界和关闭条件。
- `rtl/rgb565_word_to_axis4_adapter.sv`：M3-B 板级无关 128-bit 到 4-byte staging beat 适配。
- `tb/tb_rgb565_word_to_axis4_adapter.sv`：M3-B 字节顺序、keep、事件和背压自检。
- `rtl/rgb565_axis4_frame_accounting.sv`：M3-B 帧有效字节/beat/错误统计描述符。
- `tb/tb_rgb565_axis4_frame_accounting.sv`：帧统计描述符自检。
- `rtl/ov5640_dvp_rgb565_dma_staging_pipeline.sv`：OV5640 到 staging/帧描述符联合 wrapper。
- `tb/tb_ov5640_dvp_rgb565_dma_staging_pipeline.sv`：联合数据路径自检。
- `rtl/rgb565_axis4_mwr_descriptor.sv`：板级无关的规范化 PCIe Memory Write 请求描述符。
- `tb/tb_rgb565_axis4_mwr_descriptor.sv`：请求地址递增、keep、last 和 4 KB 边界自检。
- `rtl/rgb565_axis4_pcie_mwr_bridge.sv`：规范化请求到已审计 PCIe Memory Write 请求脚的临时桥接。
- `tb/tb_rgb565_axis4_pcie_mwr_bridge.sv`：请求锁存、字段保持和 ack 释放自检。
- `rtl/rgb565_axis4_ddr3_write_descriptor.sv`：staging beat 到规范化 128-bit DDR3 写记录。
- `tb/tb_rgb565_axis4_ddr3_write_descriptor.sv`：写数据、写掩码、记录保持和释放自检。
- staging、帧统计和规范化请求描述符已完成同域行为验证；尚未接入 CDC、DDR3 或 PCIe IP。

## 运行

```powershell
.\scripts\run_m1a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m2a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_accounting.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_integration.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_mwr_descriptor.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pcie_mwr_bridge.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ddr3_write_descriptor.ps1 -SimulatorExecPath '<questa-bin-dir>'
```

运行态只写入 `main_ov5640_pcie/build/`。`vsim.exe`、`vlog.exe` 和许可证配置由本机
环境提供，不写入仓库。当前切片不生成 PDS/IP/位流，也不证明 SCCB、板级电气时序、
CDC/FIFO、DDR3 或 PCIe 集成。M3-A 的 128-bit 布局不等同于厂商 PCIe AXIS
`tkeep` 或主机内存字节序，M3-B 适配层必须按独立合同冻结转换规则后再实现。
