> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`
- evidence_gap: PCIe 相对路径构建入口已落地但尚待新构建验证；另外两个工程、仿真库和 CI Gate 尚未落地。
- responsibility: 定义 PDS 2022.2-SP6.4 的实现流程、ModelSim/QuestaSim 四级仿真流程及三工程整改门槛。

## Verilog/SystemVerilog 注释规范

- implementation_status: documented
- code_path: null
- evidence_path: `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`
- evidence_gap: 现有厂商代码和历史 RTL 尚未进行全量合规检查。
- responsibility: 约束后续手写 RTL 的意图、接口、FSM、复位、CDC/RDC 和风险注释。

## OV7725 HDMI 顶层

- implementation_status: implemented_with_timing_failures
- code_path: `41_ov7725_hdmi/rtl/`
- entry_path: `41_ov7725_hdmi/rtl/ov7725_hdmi.v`
- project_path: `41_ov7725_hdmi/prj/ov7725_hdmi.pds`
- constraint_path: `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`
- evidence_path: `41_ov7725_hdmi/prj/report_timing/ov7725_hdmi.rtr`
- evidence_gap: 无顶层自检 testbench、PNR 功能网表或 SDF；现有位流不能证明时序合格。
- responsibility: 将 OV7725 像素流经异步 FIFO 和 DDR3 帧缓存送往 HDMI/TMDS 输出。
- high_attention: `cam_pclk`、DDR `ui_clk`、`pixel_clk` 间 CDC，以及 `ddr3_init_done` 参与的复位释放。

## DDR3 外层工程

- implementation_status: incomplete_shell
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.idf`
- evidence_gap: 外层没有明确产品 RTL、逻辑约束或实现产物。
- responsibility: 当前仅承载 DDR3 IP 引用；后续必须明确真正板级顶层和功能范围。

## DDR3 IP 示例

- implementation_status: implemented_example_only
- code_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/`
- entry_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/example_design/rtl/test_ddr.v`
- project_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.pds`
- evidence_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/place_route/test_ddr_timing_summary_after_hold_fix.txt`
- evidence_gap: 示例 testbench 与当前顶层失配，且没有 PNR 功能网表或 SDF；板级 I/O 时序覆盖不足。
- responsibility: 厂商 DDR3 Controller/PHY 的参考写读测试设计，不等同于外层产品工程。

## PCIe DMA 顶层

- implementation_status: implemented_with_known_functional_gap
- code_path: `pcie_dma_test_100h/hdl/`
- entry_path: `pcie_dma_test_100h/hdl/pcie_dma_test.v`
- project_path: `pcie_dma_test_100h/pcie_dma_test.pds`
- constraint_path: `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`
- evidence_path: `pcie_dma_test_100h/place_route/pcie_dma_test_timing_summary_after_hold_fix.txt`
- evidence_gap: 新 SP6.4 全流程、STA、PNR 网表、SDF 和位流已生成；顶层仍无四级集成仿真，UART2APB 的 `rxd` 被绑 0，SCBV 未配置，关键外部端口仍未约束。
- responsibility: 集成 PCIe x2 IP、DMA、RAM/FIFO 与 UART2APB 管理路径。
- build_entry: `pcie_dma_test_100h/scripts/run.ps1`
- build_definition: `pcie_dma_test_100h/scripts/build.tcl`
- build_gate: `pcie_dma_test_100h/scripts/check_build.ps1`
