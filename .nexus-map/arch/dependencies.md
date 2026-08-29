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
  OVAudit["CDC_RDC_AUDIT.md\nO0-A 决策证据"] --> OVTop
  OVAudit --> OVBuild["O0-B\n16 RTL + 4 IDF + 1 FDC"]
  OVBuild --> OVGate["O1-B: strict=1 / baseline=0\n七组精确失败，不可发布"]
  OVHygiene["RTL_HYGIENE_AUDIT.md\nO1-A: 39 = 1+4+26+6+2"] --> OVTop
  OVHygiene --> OVFix["O1-B 已完成\n38 条消失 / mem_a 1 条"]
  OVFix --> OVResetAudit["O2-A\nserializer reset 域契约"]
  OVResetAudit --> OVResetFix["O2-B\n关闭 OSERDES recovery 8/8"]
  OVResetFix --> OVDomainReset["O2-C\n其余逐域复位"]
  OVBoard["H3 板级 DDR3 事实"] -. "决定 14/15 bit" .-> OVMemA["O1-C mem_a"]

  DDRBringup["ddr3_test\n临时 bring-up 工程"] --> DDRIdf["ddr3.idf\n厂商 IP"]
  DDRBringup --> DDRExample["test_ddr\n临时 bring-up 顶层"]
  DDRBringup --> DDRFdc["ddr_test.fdc + ddr3.rcf\n约束基线"]
  DDRBringup --> DDRGate["check_build.ps1\n严格 / baseline gate"]
  DDRBoard["板级批准参数清单\n当前缺失"] -. "关闭已知阻断" .-> DDRGate
  DDRContract["D2 有限自检契约\n只读决策完成"] --> DDRTop["ddr3_bringup_top.sv\n计划新增"]
  DDRContract --> DDRBist["ddr3_finite_bist.sv\n计划新增"]
  DDRBist --> DDRIdf
  Standard --> DDRTop
  Standard --> DDRBist
  Questa -. "D3 后待验证" .-> DDRContract

  PCIeTop["pcie_dma_test\n顶层"] --> PCIeIP["PCIe x2 IP"]
  PCIeTop --> DMA["DMA + RAM/FIFO"]
  PCIeTop --> UART["UART2APB"]
  PCIeTop --> PCIeFdc["pcie_dma_test.fdc"]

  OVTop --> PDS["PDS 2022.2-SP6.4"]
  DDRExample --> PDS
  PCIeTop --> PDS
  PDS --> Reports["综合网表 / PNR 网表 / SDF / 位流"]
  Reports -. "待外部仿真与 SDF 标注" .-> Questa["ModelSim/QuestaSim"]
  HandRTL -. "待补顶层自检 TB" .-> Questa
```

## 关键依赖约束

- 三工程的有效器件目标应与板卡实物一致；当前审计基线为 `Logos2 / PG2L100H / FBG484 / -6`。
- 厂商 `.idf`、生成 RTL 和 PDS 仿真库属于外部生成依赖，不应被误当作独立手写逻辑。
- OV7725 O0-A 已识别 `sys_clk`、`i2c_dri_clk`、`cam_pclk`、`pixel_clk`、`pixel_clk_5x`、`clk_50m/ref_clk` 和 `ui_clk`；证据入口为 `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`。
- `wr_load` 与 `rd_load` 当前被多个逻辑独立采样；write FIFO 数据方向为 `cam_pclk → ui_clk`，read FIFO 为 `ui_clk → pixel_clk`，两者均需把复位分别在读写时钟域同步释放。
- OV7725 O1-B 已固定 16 个手写 RTL、4 个活动 IDF 和唯一顶层 FDC，从空 `build/` 完成 SP6.4 七阶段，进程退出 0、日志 `E: 0`、warning `4067`、critical `81`，并生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`。
- OV7725 O1-B 已消除 38 条确定性手写 RTL 位宽告警，只剩精确的 `ddr3_ip.mem_a` 1 条；严格 gate 返回 1，baseline 仅在七组 corner/check/clock pair/endpoints 精确匹配时返回 0，且继续标记不可发布。
- 高有效 reset 已驱动四个 serializer 内的八个 OSERDES，并新增 Slow Recovery `pixel_clk → pixel_clk_5x` `-0.643 ns / -4.191 ns / 8/8`。该组不是批准例外，依次转入 O2-A reset 域契约、O2-B 局部实现和 O2-C 其余逐域复位。
- `mem_a` 不属于 O1-B：活动 IP 是 14 bit，顶层/FDC 是 15 bit，综合网表把第 15 bit 绑 0。该冲突转入 H3/O1-C，必须依据 DDR3 料号、组织和原理图决定收窄 RTL/FDC 或重生成 IP。
- OV7725 O1-B 未修改 `mem_a`、厂商 IP、FDC、CDC/RDC、FIFO 或时序例外；O2-A/O2-B/O2-C 必须继续遵守逐域复位和禁止宽泛 false path 的契约。
- DDR3 新入口已用 `test_ddr`、`ddr3.idf`、FDC 和 RCF 从空 `build/` 完成七阶段全流程，内部 STA 为 `All Constraints Met`，且综合网表、PNR 网表、SDF 和位流均非零。
- DDR3 严格 gate 因 BIST 位宽/dangling、`rst_board` share pin、BANKR4 VCCIO 3.3、UART I/O 以及输入/输出 timing 共 7 类阻断返回 1；显式 baseline 放行返回 0 但不可发布。日志无 SCBV 命中不等同于板级参数获批，批准清单仍是关闭 gate 的前置依赖。
- DDR3 D2 只读决策不依赖修改厂商示例：`test_ddr`、持续运行 BIST 和旧 testbench 保持原样；D3 若获审核，只新增项目自有 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`。
- 有限自检契约固定 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，pair/run timeout 分别为 4096/131072 周期；签核依赖稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息，而不是厂商 LED 或内部层级。
- 新项目自有 DDR3 RTL 依赖根目录 VSCS；厂商 `ip_core/ddr3/**` 仍作为外部生成依赖，不因 D2 决策被改写。
- PCIe 顶层依赖专用 HSST/IP 约束；UART2APB 是否保留是后续 RTL 与 FDC 的共同决策点。
- 仿真流程依赖编译后的 Logos2 USIM/VSIM 库和可用的 `vsim.exe`/`vlog.exe`；当前环境不满足该依赖。
