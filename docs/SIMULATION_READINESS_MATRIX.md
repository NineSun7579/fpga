# 三项目仿真就绪度矩阵

更新日期：2026-09-01

适用工具：PDS `2022.2-SP6.4`、外部 ModelSim/QuestaSim

## 结论

DDR3 当前仍没有面向项目集成顶层的仿真入口。摄像头产品目标已固定为双 OV5640；`59_top_dual_ov5640_hdmi/` 已建立 C1-A README 和板级证据清单，但没有导入 RTL/TB。`origin/parallel_driver@485f3bb` 可见 4 个相关 TB 和两项数据面 PASS 自述，尚无本仓库 canonical `.f/.do`、run marker 和日志门禁，因此仍未形成可审核项目仿真入口。Questa Sim-64 `2021.1`、Logos2 USIM/VSIM 和 `V_BUF` 原语 smoke 已验证，许可证配置保持在仓库外部。PCIe S2-A 最新归档边界回归 run id `add7efa39f644384af9929e8a9366739` 的 RTL 编译为 `0 errors/0 warnings`，elaboration 成功，仿真运行到 `1476105 ns`，同一 run marker、唯一 `TEST PASS` 和 PowerShell 退出码 0 均通过。当前 PG2L50H 完整 PDS run id `9952da4164f040d5924a558baa5cd8ca` 为 complete/valid，43 输入/9 证据，baseline/strict gate=`0/1`、最差 slack `0.100 ns`；S2-B run `30bad6e164be4a4b8284a00f1e96bd87` 已通过真实 RC/EP link-up。PCIe S2-D 综合后受限 smoke run `41135fd3fadd4c51a70508a6fa5af3e3` 使用当前 canonical 综合网表，唯一 marker/PASS 和退出 0 均通过。S2-E PNR 功能 run `927abae8ed7d40aeb5d6f706b3723e0a` 运行至 `491965 ns`，唯一 marker/PASS、`Errors: 0, Warnings: 1` 和退出 0 均通过。S2-F 已完成 SDF 标注与无 force 动态复验，但因两个正 timing error、GLS/STA 冲突和负模型语义缺口保持 blocked。所有 ini、work、日志、transcript 与波形只在各项目 `build/`。DDR3、双 OV5640、S2-C Endpoint 主动 DMA，以及 DDR3/双 OV5640 的 SDF 时序仿真仍待完成。

项目级仿真必须在各工程自身 `sim/questa/` 下归档相对路径 filelist、DO 脚本和自检 testbench；双 OV5640 使用 `59_top_dual_ov5640_hdmi/sim/questa/`，不得放入 OV7725 legacy 目录。版本库只保留可复现源，不提交 `.mpf`、`sim_*` 编译库或任何运行态文件。不得批量修改 `ipcore/`、`ip_core/`、`ip_backup/` 下的厂商生成文件，也不得把厂商示例顶层改名后冒充集成验证。

## 总览

| 项目 | 项目级 TB | 项目级 `.f/.do` | 厂商示例资产 | 当前最高阻断 | 进入动态仿真的前置 |
|---|---:|---:|---|---|---|
| 摄像头 HDMI（双 OV5640） | C1-A 文档型项目已建立；C0 已审计 4 个参考 TB，尚未导入 | 无 canonical `.f/.do` | 双 OV5640 参考 TB；OV7725 legacy 基础设施 | C1 板级接口未冻结、参考 TB force init、PASS 未复验 | 关闭 C1、建立独立 `sim/questa/` 和双路输入合同 |
| DDR3 | 无 | 无 | DDR3 `test_ddr`/memory model 示例 | 旧 TB 端口失配 | D3-A/B/C 项目自有 BIST/top |
| PCIe DMA | S2-A 受控 TB；S2-B 真实 RC/EP TB；S2-C 诊断 TB；S2-D 综合后 TB；S2-E PNR 功能 TB | `behav`、`link`、`dma`、`post_syn`、`post_pnr_func` 五组 `.f/.do` | `pango_pcie_top` RC/EP 示例 | S2-C BAR1、H2-B1、SDF 时序 | BAR1 与 PNR 时序分别推进 |

## 摄像头 HDMI：OV7725 legacy 与双 OV5640 目标

### 已发现资产

- legacy 设计顶层为 `41_ov7725_hdmi/rtl/ov7725_hdmi.v`，不能改名冒充 OV5640。
- `59_top_dual_ov5640_hdmi/` 已建立 README 与板级证据清单，但没有 RTL、IP、FDC、PDS 或 TB；它是 C1-A 产品边界，不是可编译工程。
- `origin/parallel_driver@485f3bb` 已提供双 OV5640 参考实现，包含 `top_dual_ov5640_hdmi`、两路独立 SCCB/RESET/PWDN/DVP、每路 960×1080 半幅、双写 DDR3 通道、HDMI/PCIe 数据路径及约束；尚未选择性导入。
- C0 逐文件审计已经完成，见 [`OV5640_C0_REFERENCE_AUDIT.md`](OV5640_C0_REFERENCE_AUDIT.md)；17 个 HDMI 明文 RTL、4 个 TB、4 个 PCIe video 参考文件、PDS/IP/FDC 和排除资产均已登记，但未导入产品工程。
- 参考分支提供 `sim/tb/Video_Image_Simulate_CMOS.v`、`tb_ov5640_dri.v`、`tb_dual_ov5640_dri.v` 和 `tb_rgb565_to_axis128.v`；README 自述双摄采集环路和 RGB565→AXI128/BAR2 通过，但未提供本仓库 canonical `.f/.do` 与受控日志证据。`tb_dual_ov5640_dri.v` 还直接 force 两路 `cam_init_done`，只覆盖驱动级像素计数，且成功字符串不是仓库要求的唯一 `TEST PASS`。
- 活动 IP 示例位于 `41_ov7725_hdmi/prj/ipcore/ddr3_ip/example_design/bench/`，并配有 `sim/modelsim/sim_file_list.f` 与 `sim/modelsim/ctrl_phy_sim.tcl`。
- `prj/ipcore/` 下还存在 PLL、FIFO 的厂商示例 testbench，但它们只验证单个 IP，不覆盖 `ov7725_hdmi` 集成数据通路。

### 缺口与风险

- 当前产品目录没有 `sim/questa/`、相对路径 `.f/.do`、受控启动器或门级 SDF 入口。
- 参考分支跟踪了 `sim_*` Questa 编译库和带本机绝对路径的生成文件；这些必须排除，不能整体合并。
- DDR3 示例 filelist 面向 `ddr3_test_top_tb`/`test_ddr`，不包含摄像头输入、帧缓存切换和 HDMI 输出检查。
- `ctrl_phy_sim.tcl` 含历史绝对路径；不能在另一台 Windows 主机上直接复用。
- 双摄拓扑已经由 owner 固定；参考设计的两路独立 SCCB/RESET/PWDN 与 100H 管脚约束尚未对照实际板卡，两路模组料号、DVP 格式、960×1080 半幅/1920×1080 拼接和帧率也未完成产品审核。本仓库仍没有项目级唯一 `TEST PASS`、受控 run marker 和完整退出契约。

### TODO（S3）

1. 先按 [`OV5640_C0_REFERENCE_AUDIT.md`](OV5640_C0_REFERENCE_AUDIT.md) 和 [`双 OV5640 板级证据清单`](../59_top_dual_ov5640_hdmi/doc/BOARD_EVIDENCE.md) 关闭 C1 双路产品/板级输入，再从登记候选中选择性导入，不得导入生成物与编译库。
2. 在新工程自己的 `sim/questa/` 下归档经审核的 4 个参考 TB，补项目集成 TB、相对路径 filelist 和四级 DO；不得直接改名复用 OV7725 TB 计划。
3. 覆盖双路读 ID/配置、独立/并发采集、每路 960×1080 半幅与 1920×1080 左右拼接、复位、DDR 初始化延迟、双写通道、帧切换/读出、HDMI 有效区和 FIFO 边界。
4. 为每个级别加入超时、错误计数、唯一 `TEST PASS` 和非零失败退出；C3 锁定后再接入综合网表、PNR 功能网表和 SDF。

## DDR3

### 已发现资产

- 活动 IP 位于 `ddr3_test/ddr3_test/ip_core/ddr3/`，示例顶层为 `example_design/rtl/test_ddr.v`。
- 厂商示例 testbench 和 memory model 位于 `example_design/bench/`，并配有 `sim/modelsim/sim_file_list.f`、`sim/modelsim/ctrl_phy_sim.tcl`。
- 当前 filelist 面向 `ddr3_test_top_tb` 与厂商 `test_ddr`，不是规划中的 `ddr3_bringup_top`/`ddr3_finite_bist`。

### 缺口与风险

- 没有项目级自检 TB；旧 TB 的端口和当前 wrapper 已失配，不能直接作为验收入口。
- `ctrl_phy_sim.tcl` 含历史 `D:/pango/PDS_2022.2-SP6.4/...` 路径。
- 现有示例包含 FSDB/Verdi 等环境假设，且未提供稳定的 CI 退出码契约。
- D3-A/B/C 尚未实现项目自有有限 BIST，因此综合后和 PNR 两级没有应验收的项目网表顶层。

### TODO（S1）

1. 依 D3-0 契约新增 `ddr3_bringup_top.sv`、`ddr3_finite_bist.sv` 和 `tb_ddr3_finite_bist.sv`。
2. 使用相对路径 filelist/DO，保留 `I_ips_ddr_top` 和厂商 `ip_core/ddr3/**` 原样。
3. 覆盖初始化、16 个有限写读比较 pair、数据错误、写/读超时及稳定 done/error 信号。
4. D3-C 完成七阶段 PDS 回归后，再执行综合后、PNR 功能和 PNR 时序仿真。

## PCIe DMA

### 已发现资产

- 项目顶层为 `pcie_dma_test_100h/hdl/pcie_dma_test.v`。
- 厂商示例位于 `pcie_dma_test_100h/ipcore/pcie_test/example_design/bench/`，testbench 为 `pango_pcie_top_tb.v`。
- 对应 filelist/DO 为 `ipcore/pcie_test/sim/modelsim/pango_pcie_top_filelist.f` 和 `pango_pcie_top_sim.do`。
- S2-A 项目资产位于 `sim/questa/tb/tb_pcie_dma_test.sv`、`sim/questa/tb/pcie_test_smoke_model.sv`、`sim/questa/behav.f` 和 `sim/questa/run_behav.do`；静态门禁为 `scripts/check_sim.ps1`。
- S2-B 项目资产位于 `sim/questa/tb/tb_pcie_dma_link.sv`、`sim/questa/link.f`、`sim/questa/link_vendor_local.f`、`sim/questa/compile_vendor_link.do` 和 `sim/questa/run_link.do`；静态门禁为 `scripts/check_link_sim.ps1`。
- S2-D 项目资产位于 `sim/questa/tb/tb_pcie_dma_post_syn.sv`、`sim/questa/post_syn.f` 和 `sim/questa/run_post_syn.do`；静态门禁为 `scripts/check_post_syn_sim.ps1`，契约为 [`S2D_POST_SYN_SMOKE.md`](../pcie_dma_test_100h/doc/S2D_POST_SYN_SMOKE.md)。
- S2-E 项目资产位于 `sim/questa/tb/tb_pcie_dma_post_pnr_func.sv`、`sim/questa/post_pnr_func.f` 和 `sim/questa/run_post_pnr_func.do`；静态门禁为 `scripts/check_post_pnr_func_sim.ps1`，契约为 [`S2E_POST_PNR_FUNC_SMOKE.md`](../pcie_dma_test_100h/doc/S2E_POST_PNR_FUNC_SMOKE.md)。
- S2-F 项目资产位于 `sim/questa/tb/tb_pcie_dma_post_pnr_timing.sv`、`sim/questa/post_pnr_timing.f` 和 `sim/questa/run_post_pnr_timing.do`；静态门禁为 `scripts/check_post_pnr_timing_sim.ps1`。独立 `level1/level2/level3` 诊断入口及门禁不会修改 canonical 验收配置；阻断报告为 [`S2F_POST_PNR_TIMING_SMOKE.md`](../pcie_dma_test_100h/doc/S2F_POST_PNR_TIMING_SMOKE.md)，solver 证据见 [`S2F_NEGATIVE_TIMING_DIAGNOSTIC.md`](../pcie_dma_test_100h/doc/S2F_NEGATIVE_TIMING_DIAGNOSTIC.md)。

### 缺口与风险

- 示例 TB 针对 `pango_pcie_top` RC/EP，不实例化项目 `pcie_dma_test`，不能证明 DMA、RAM/FIFO 和 UART 管理路径。
- `pango_pcie_top_sim.do` 含大量历史绝对路径，filelist 与工作目录耦合。
- S2-A 受控模型只验证项目顶层外壳、复位链和 LED 域；其 link indication 不是真实 LTSSM、TLP、DMA 或板级链路证据。
- S2-B 已参数化厂商加密模型并以 `pango_pcie_top_sim` 为 RC；动态 run 在首次速率重训练后取得连续 32 周期双端 link-up/L0，并通过唯一 marker/PASS 和退出码门禁。S2-C 已建立归档入口和静态合同，但当前活动 IP 的 BAR1 被禁用，厂商 Endpoint DMA 命令窗口不可达；不得用 RC 主动 BAR0 往返冒充最终 S2-C。
- Questa `2021.1` 与 Logos2 USIM 已验证；S2-A 仅在仿真专用 `sim/questa/behav.f` 中补入 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`，未修改由 IDF 管理的 canonical PDS 源清单。动态 smoke 的 RTL 编译为 0 errors/0 warnings，elaboration 成功并运行到 `1476105 ns`，同一 run marker、唯一 `TEST PASS` 和 PowerShell 退出码 0 均通过。
- 当前复验确认 Questa 版本、S2-A/S2-B 静态 gate 和现有 USIM/VSIM 目录；S2-A 以新 `SIM_RUN_ID` 动态通过，不复用历史 transcript。
- S2-A RTL hygiene 已贯通 DMA `o_trgt1_radm_pkt_halt` 到 hard-IP RX halt 输入。Questa 为 `0 warnings`；PDS 原两条未连接端口 warning 消失，只保留 bit2 恒 0 的两条优化/清理 warning。受控 link indication 仍不证明真实 LTSSM、TLP、DMA 或板级链路。
- 活动 PCIe IP、PDS 目标和新构建产物均与实际 PG2L50H 一致；lane/refclk/PERST#/SCBV 和 UART 决策继续由 H2-B1 阻断。
- S2-D 已用当前 canonical 综合网表完成受限动态 smoke，只证明综合网表展开、项目 reset debounce/sync 与 reference-clock LED counter 路径；强制 link 观察网络不构成 LTSSM、DMA、PNR、SDF 或时序证据。
- S2-E 已生成并绑定不含 `$sdf_annotate` 的独立 PNR 功能网表；Questa run `927abae8ed7d40aeb5d6f706b3723e0a` 动态通过，只证明网表展开、reset debounce/sync 和 reference-clock LED counter 路径，不构成链路、DMA、SDF/时序、H2-B1 或发布证据。
- S2-F run `7fc77a7ec8db479db7332e8037426d6c` 由独立启动器复验，成功标注 SDF，但无 force 仍在 HSST `ext_rstn_debounce` 自然复现两个正 setup/hold error；另有 1590 个 `V_DRM18K_E1` 负限制无法求解和 1 个 `V_FFASYN` delayed-copy 告警。solver 矩阵 run `f79dc238c12949b7b67db2ef0d0ddd0b` 中，`level1/2/3` 仍各有同一个 setup/hold error，`vsim-3004` 分别为 `3624/1590/1590`。GLS 与 slow-corner STA 全正裕量冲突，既不能标记通过，也不能据此断言硅上失败。

### TODO（S2）

1. S2-A 静态、动态 smoke 和 RX halt RTL hygiene 已完成；生成 wrapper 重生成后必须重跑接口 gate。
2. S2-B 静态与动态真实链路已完成；生成 IP 或仿真模型变化后必须重跑 32 周期稳定窗口和 watchdog 门禁。
3. S2-C 在已通过的真实链路上增加一次可预测 DMA 写读回；LTSSM、完成状态、数据和超时失败均 `$fatal`。
4. 综合后与 PNR 功能受限结构 smoke 已完成；PNR 时序入口和 SDF 层级已锁定，但动态结果被两个正 timing error 与负模型语义缺口阻断，需厂商确认兼容模型后按原合同复验。

## 四级仿真共同门槛

| 级别 | 必须具备 | 失败判定 |
|---|---|---|
| 行为级 | 项目 RTL、相对路径 filelist、集成 TB、USIM | 编译/运行非零、超时、数据错误或无唯一 PASS |
| 综合后 | PDS 综合网表、同一 TB、USIM | 网表编译失败、层级不符或自检失败 |
| PNR 后功能 | PNR 功能网表、USIM+VSIM、同一 TB | 缺少 VSIM 原语、网表编译失败或自检失败 |
| PNR 后时序 | PNR 网表、slow-corner SDF、USIM+VSIM | SDF annotation error、实例匹配错误、未批准 timing violation 或自检失败 |

所有 DO 脚本都必须：从工程根目录启动、建立独立 `build/sim/<level>/<run-id>/work`、写入 `build/logs/`、遇到错误 `quit -code 1 -force`，并在成功路径只允许一个 `TEST PASS`。SDF 层级必须以实际 testbench DUT 实例为准，不能照抄厂商示例层级。

## 依赖顺序

```text
S0-1 Questa、USIM、VSIM 已验证
        ├─ S1 DDR3：D3-A → D3-B → D3-C → D4
        ├─ S2 PCIe：S2-A/S2-B 已完成 → S2-C → 后级网表仿真
        └─ S3 双 OV5640：C0/C1 → 选择性导入 → 项目内 sim/questa → 集成 TB → 四级仿真
```

S0-1 完成只证明公共仿真器和 Pango 原语库可用，不替代任何项目级 `TEST PASS`、后级网表或 SDF 标注。厂商示例保留为参考证据；所有项目验收必须由项目自有顶层和自检 TB 完成。
