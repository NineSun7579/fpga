> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: manual inspection of current source tree and PDS artifacts

# Dependencies

```mermaid
flowchart TD
  Guide["README.md\nPDS/仿真指南"] --> Todo["TODO.md\n整改与验收门槛"]
  Standard["VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md"] --> HandRTL["后续手写 RTL/TB"]

  OVTop["ov7725_hdmi\n顶层"] --> Camera["OV7725 采集"]
  OVTop --> OVFifo["异步 FIFO"]
  OVTop --> OVDDR["DDR3 IP"]
  OVTop --> HDMI["HDMI/TMDS"]
  OVTop --> OVFdc["ov7725_hdmi.fdc"]

  DDRShell["ddr3_test.pds\n外层 IP 壳"] --> DDRIdf["ddr3.idf"]
  DDRIdf --> DDRExample["test_ddr\n厂商示例"]
  DDRExample --> DDRFdc["ddr_test.fdc"]

  PCIeTop["pcie_dma_test\n顶层"] --> PCIeIP["PCIe x2 IP"]
  PCIeTop --> DMA["DMA + RAM/FIFO"]
  PCIeTop --> UART["UART2APB"]
  PCIeTop --> PCIeFdc["pcie_dma_test.fdc"]

  OVTop --> PDS["PDS 2022.2-SP6.4"]
  DDRExample --> PDS
  PCIeTop --> PDS
  PDS --> Reports["综合网表 / PNR 报告 / 位流"]
  Reports -. "待补 PNR 网表与 SDF" .-> Questa["ModelSim/QuestaSim"]
  HandRTL -. "待补顶层自检 TB" .-> Questa
```

## 关键依赖约束

- 三工程的有效器件目标应与板卡实物一致；当前审计基线为 `Logos2 / PG2L100H / FBG484 / -6`。
- 厂商 `.idf`、生成 RTL 和 PDS 仿真库属于外部生成依赖，不应被误当作独立手写逻辑。
- OV7725 工程的摄像头、DDR UI 与 HDMI 时钟域互相依赖 CDC 和复位策略，必须先修结构再声明时序例外。
- DDR3 外层工程依赖 IP 示例，但示例通过不能替代外层顶层、板级约束和产品自检。
- PCIe 顶层依赖专用 HSST/IP 约束；UART2APB 是否保留是后续 RTL 与 FDC 的共同决策点。
- 仿真流程依赖编译后的 Logos2 USIM/VSIM 库和可用的 `vsim.exe`/`vlog.exe`；当前环境不满足该依赖。
