> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`
- evidence_gap: 三项目均已建立 SP6.4 可重复全流程与严格/baseline gate 证据；OV7725 当前因明确负时序不可发布，仿真库和三项目四级仿真尚未完成。
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
- evidence_path: `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`, `41_ov7725_hdmi/build/logs/pds-gen_bit_stream.log`, `41_ov7725_hdmi/build/pds/report_timing/ov7725_hdmi.rtr`, `41_ov7725_hdmi/scripts/check_build.ps1`
- evidence_gap: O0-A 静态 CDC/RDC 审计与 O0-B SP6.4 七阶段实现、网表/SDF/位流及 gate 基线已完成；最终 STA 明确失败，顶层自检和四级仿真尚未完成，当前结果不可发布。
- responsibility: 将 OV7725 像素流经异步 FIFO 和 DDR3 帧缓存送往 HDMI/TMDS 输出。
- clock_domains: `sys_clk`, `i2c_dri_clk`, `cam_pclk`, `pixel_clk`, `pixel_clk_5x`, `clk_50m/ref_clk`, `ui_clk`
- cdc_findings: `wr_load`/`rd_load` 被多个逻辑独立采样；write FIFO 为 `cam_pclk → ui_clk`，read FIFO 为 `ui_clk → pixel_clk`
- rdc_findings: 两个异步 FIFO 的帧复位从单一源域同时驱动两侧；`ddr3_init_done` 和组合顶层复位未逐域同步释放
- build_inputs: 16 个手写 RTL、4 个活动 IDF、1 个顶层 FDC；器件固定为 `Logos2 / PG2L100H / FBG484 / -6`
- build_status: SP6.4 七阶段进程退出 0，日志 `E: 0`；严格 gate 失败，显式 baseline gate 通过并标记不可发布
- timing_findings: `Some Constraints Violated`；慢角 setup `-7.344 ns / TNS -132.832 ns / 20`、read FIFO 方向 setup `-2.275 ns / TNS -24.111 ns / 11`、recovery `-4.263 ns / TNS -202.445 ns / 53`；快角仍为相同三组失败端点
- artifact_evidence: synthesis netlist `6,873,287` bytes; PNR netlist `11,600,361` bytes; SDF `8,894,116` bytes; `.sbit` `3,791,112` bytes; `.bin` `3,789,476` bytes
- remediation_contract: 逐域异步置位/同步释放复位；帧事件只同步一次后在目标域扇出；FIFO 两侧复位分别在本地域释放；仅在结构闭环后对厂商认证路径添加精确例外
- next_step: D2 有限自检契约评审；OV7725 O1-A 只读 RTL 卫生评审
- high_attention: `i2c_dri_clk` 逻辑生成时钟、`cam_pclk`/DDR `ui_clk`/`pixel_clk` 间业务 CDC、FIFO 分侧复位，以及 `ddr3_init_done` 参与的复位释放。

## DDR3 外层工程

- implementation_status: bringup_full_implementation_baseline
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/build/logs/pds-gen_bit_stream.log`, `ddr3_test/ddr3_test/build/pds/report_timing/test_ddr.rtr`, `ddr3_test/ddr3_test/scripts/check_build.ps1`
- evidence_gap: SP6.4 全流程、STA、综合网表、PNR 网表、SDF 和位流已验证；严格 gate 因 7 类已知阻断返回 1，显式 baseline 放行返回 0 但不可发布。板级批准参数清单、产品功能和四级仿真仍未验收。
- responsibility: 当前以厂商 `test_ddr` 作为临时 DDR3 board bring-up 顶层；后续必须明确真正产品顶层和板级功能范围。
- provisional_build_entry: `ddr3_test/ddr3_test/scripts/run.ps1`
- build_definition: `ddr3_test/ddr3_test/scripts/build.tcl`
- build_gate: `ddr3_test/ddr3_test/scripts/check_build.ps1`
- provisional_top: `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`
- constraint_baseline: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr_test.fdc`, `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.rcf`
- timing_evidence: `All Constraints Met`; slow-corner setup WNS `0.678 ns`, TNS `0`; hold `0.137 ns`; recovery `4.578 ns`; removal `0.351 ns`
- artifact_evidence: synthesis netlist `5,914,586` bytes; PNR netlist `9,734,239` bytes; SDF `9,130,393` bytes; `.sbit` `3,791,112` bytes; `.bin` `3,789,476` bytes
- strict_gate_blockers: BIST error-data width mismatch, BIST dangling cleanup, `rst_board` share pin, BANKR4 VCCIO 3.3 incompatibility, UART I/O constraints missing, input timing missing, output timing missing
- scbv_status: 当前 DDR3 完整构建日志无 SCBV 命中

## DDR3 IP 示例

- implementation_status: implemented_example_only
- code_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/`
- entry_path: `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`
- project_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.pds`
- evidence_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/place_route/test_ddr_timing_summary_after_hold_fix.txt`
- evidence_gap: 外层重建已生成当前 `test_ddr` 的 PNR 网表与 SDF，但示例 testbench 仍与顶层失配，SDF 尚未由外部仿真器标注验证，板级 I/O 时序覆盖不足。
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
