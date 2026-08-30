> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
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
  OVFix --> OVResetAudit["O2-A 已完成\n联合释放契约 / 8 endpoints"]
  OVResetAudit --> OVResetRejected["O2-B 已否决并回退\ncompile + 七阶段 / Recovery 失败"]
  OVResetRejected --> OVBaseline["O2-D1-R\n回退基线重建"]
  OVBaseline --> OVResetReview["O2-D1-G\ngenerated-clock / 状态契约"]
  OVResetReview --> OVResetImpl["O2-D2\n审核后只执行一次"]
  OVResetImpl --> OVMemA["O1-C mem_a"]
  OVMemA --> OVInitSync["O3-A\n同步 ddr3_init_done"]
  OVInitSync --> OVDomainReset["O2-C1\n普通时钟域本地复位"]
  OVDomainReset --> OVFifoReset["O2-C2\nFIFO reset/flush"]
  OVFifoReset --> OVEventCdc["O3-B\n帧事件 CDC"]
  OVFifoReset --> OVTimingClose["O4\n约束与时序闭环"]
  OVEventCdc --> OVTimingClose
  OVBoard["H3 板级 DDR3 事实"] -. "决定 14/15 bit" .-> OVMemA

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
- 高有效 reset 已驱动四个 serializer 内的八个 OSERDES。O2-B 曾按 O2-A 契约级联 `pixel_clk_5x` 两级释放并完成 compile/七阶段，但 Slow Recovery 出现 `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8` 与 `pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`；八个反向 endpoint 正是四个 serializer 的 master/slave OSERDES `OCLKDIV` 检查。
- O2-B 已触发停止条件并完整回退；`check_build.ps1`、旧七组 baseline、FDC/RCF、PLL/IP 和时序例外均未修改。O2-D1 已否决动态门控，O2-D1-G 进一步冻结唯一候选：`CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位、每 serializer 本地 reset 复制，以及唯一 `/5` generated-clock（`u_pll_clk/clkout1` → 唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，`-edges {1 5 11}`）。
- `mem_a` 不属于 O1-B：活动 IP 是 14 bit，顶层/FDC 是 15 bit，综合网表把第 15 bit 绑 0。该冲突转入 H3/O1-C，必须依据 DDR3 料号、组织和原理图决定收窄 RTL/FDC 或重生成 IP。
- OV7725 O2-D1-R 与 O2-D1-G 已完成；当前等待用户书面审核后单次执行 O2-D2。H3 板级事实与 O2-D2 结果共同解锁 O1-C，随后按 O3-A → O2-C1 → O2-C2 → O3-B → O4 推进；O2-D2 失败即完整回退，generated-clock 解析、waveform、端点覆盖或新 baseline 失败任一不满足即停止，不扫描第二相位或增加 waiver。
- DDR3 新入口已用 `test_ddr`、`ddr3.idf`、FDC 和 RCF 从空 `build/` 完成七阶段全流程，内部 STA 为 `All Constraints Met`，且综合网表、PNR 网表、SDF 和位流均非零。
- DDR3 严格 gate 因 BIST 位宽/dangling、`rst_board` share pin、BANKR4 VCCIO 3.3、UART I/O 以及输入/输出 timing 共 7 类阻断返回 1；显式 baseline 放行返回 0 但不可发布。日志无 SCBV 命中不等同于板级参数获批，批准清单仍是关闭 gate 的前置依赖。
- DDR3 D2 只读决策不依赖修改厂商示例：`test_ddr`、持续运行 BIST 和旧 testbench 保持原样；D3 若获审核，只新增项目自有 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`。
- DDR3 D3-0（2026-08-30）已完成活动 `ddr3` 核、非标准 AXI-like AW/W/AR/R 握手和 `I_ips_ddr_top` board wrapper 边界评审；D3-A 等待用户审核后才可新增项目自有顶层。
- D3-0 只读边界：不修改 `test_ddr.v`、`ddr3.v`、任何 DDR3 IDF、FDC/RCF 或构建入口；D3-A/B/C 必须保持 `I_ips_ddr_top` 与厂商 `ip_core/ddr3/**` 原样，若接口语义、地址单位或层级变化则停止并重新审核。
- 有限自检契约固定 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，pair/run timeout 分别为 4096/131072 周期；签核依赖稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息，而不是厂商 LED 或内部层级。
- 新项目自有 DDR3 RTL 依赖根目录 VSCS；厂商 `ip_core/ddr3/**` 仍作为外部生成依赖，不因 D2 决策被改写。
- 当前执行队列为 S0-1 → H0/H1/H3 → 单次 O2-D2 → D3-A/B/C → H2-B → S1/S2/S3 → O1-C/O3/O2-C/O4；用户审核或外部资料未到位时保持对应 RTL/IP/约束只读，不以 baseline 放行替代验收。
- `docs/SIMULATION_READINESS_MATRIX.md` 已确认三个项目的项目级 TB、`.f`、`.do` 均缺失；厂商示例不形成产品顶层覆盖。S1 还依赖 D3-A/B/C 与 D4，S2 还依赖 H2-B/PG2L100H 一致性，S3 还依赖输入格式契约与 O2-D2/O3 RTL 锁定。
- PCIe 顶层依赖专用 HSST/IP 约束；UART2APB 是否保留是后续 RTL 与 FDC 的共同决策点。
- PCIe H2-A（2026-08-30）固定顶层 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`/`button_rst_n` 与两枚 LED；FDC 当前映射 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。
- H2-A 的板级证据缺口为 lane 极性、板级拓扑、I/O delay 和 SCBV；活动 `ipcore/pcie_test/pcie_test.idf` 仍标记 `Logos2/PG2L50H/FBG484/-6`，而 PDS 目标为 `Logos2/PG2L100H/FBG484/-6`，必须走 IP 重生成契约，不得静默忽略。
- UART2APB 在 `pcie_dma_test.v` 以隐式 `rxd/txd` 网络连接，当前 `rxd` 被绑 0；H2-A 只记录该功能缺口，H2-B 需先决定端口归属和板级连接。
- H2-A 只读边界：仅维护文档/证据矩阵/IP 重生成契约，不改 PCIe RTL、IDF 或 FDC；H2-B 在板级资料、器件元数据和 SCBV 均闭合前不得收紧 gate，缺口出现即停止。
- S0 环境复核（2026-08-30）确认 `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe` 存在，是唯一已发现工具；PATH、`C:/questasim64/win64` 和常见 ModelSim/QuestaSim 目录均未找到 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- S0-1 已准备 `scripts/compile_simlib.ps1` → 环境变量 → `scripts/compile_simlib.tcl` → PDS `compile_simlib` 的参数化链路，可选择 ModelSim/QuestaSim、USIM/VSIM/BOTH、family、语言、工具路径与输出目录；入口准备不等于库已生成。
- 仿真流程仍依赖可用且有许可证的 `vsim.exe`/`vlog.exe`/`vlib.exe` 与编译后的 Logos2 USIM/VSIM 库；默认运行因 `vsim.exe` 缺失在 PDS 前返回 1，动态仿真在实际编译退出 0、日志无 `E:` 且库目录非空前保持阻塞。
- CI-0 仓库级静态一致性门禁依赖根指南/TODO/VSCS、三个项目 README 与各自 `build.tcl`/`run.ps1`/`check_build.ps1`；当前工作区门禁退出码为 0，7 个 PowerShell 脚本 AST 解析错误数为 0。它只验证结构、入口与文档关系，不解除任何 PDS、STA、板级或仿真阻断。
