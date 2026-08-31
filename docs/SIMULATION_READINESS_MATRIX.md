# 三项目仿真就绪度矩阵

更新日期：2026-08-31

适用工具：PDS `2022.2-SP6.4`、外部 ModelSim/QuestaSim

## 结论

DDR3 与 OV7725 当前仍没有面向项目集成顶层的仿真入口。PCIe 已完成 S2-A 受控行为 smoke 和 S2-B 真实厂商 RC/项目 EP 的静态入口，但两者都尚未动态运行。S0-1 仍受本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断，因此本矩阵记录的是静态就绪度，不代表仿真已通过。

项目级仿真必须新增相对路径的 filelist、DO 脚本和自检 testbench；不得批量修改 `ipcore/`、`ip_core/`、`ip_backup/` 下的厂商生成文件，也不得把厂商示例顶层改名后冒充集成验证。

## 总览

| 项目 | 项目级 TB | 项目级 `.f/.do` | 厂商示例资产 | 当前最高阻断 | 进入动态仿真的前置 |
|---|---:|---:|---|---|---|
| OV7725 HDMI | 无 | 无 | DDR3、PLL、FIFO 示例 | 无摄像头/HDMI 集成 TB；S0-1 | S0-1、输入格式契约、O2-D2/O3 相关 RTL 锁定 |
| DDR3 | 无 | 无 | DDR3 `test_ddr`/memory model 示例 | 旧 TB 端口失配；S0-1 | S0-1、D3-A/B/C 项目自有 BIST/top |
| PCIe DMA | S2-A 受控 TB；S2-B 真实 RC/EP TB | `behav.f/run_behav.do`；`link.f/run_link.do` | `pango_pcie_top` RC/EP 示例 | S2-A/S2-B 仅静态通过；S0-1、DMA、H2-B1 | Questa/USIM 后运行 S2-A；厂商模型可用后运行 S2-B |

## OV7725 HDMI

### 已发现资产

- 设计顶层为 `41_ov7725_hdmi/rtl/ov7725_hdmi.v`。
- 活动 IP 示例位于 `41_ov7725_hdmi/prj/ipcore/ddr3_ip/example_design/bench/`，并配有 `sim/modelsim/sim_file_list.f` 与 `sim/modelsim/ctrl_phy_sim.tcl`。
- `prj/ipcore/` 下还存在 PLL、FIFO 的厂商示例 testbench，但它们只验证单个 IP，不覆盖 `ov7725_hdmi` 集成数据通路。

### 缺口与风险

- 没有项目级 `sim/`、`tb/`、行为级 DO 或门级 SDF 入口。
- DDR3 示例 filelist 面向 `ddr3_test_top_tb`/`test_ddr`，不包含摄像头输入、帧缓存切换和 HDMI 输出检查。
- `ctrl_phy_sim.tcl` 含历史绝对路径；不能在另一台 Windows 主机上直接复用。
- 尚未定义可重复的 OV7725 RGB565 帧模型，也没有 `TEST PASS`、超时和 `$fatal` 退出契约。

### TODO（S3）

1. 新建 `tb_ov7725_hdmi.sv` 与项目级 `sim/rtl.f`、`sim/tb.f`、四级 DO 脚本。
2. 先覆盖复位、DDR 初始化延迟、帧写入/切换/读出、HDMI 有效区和 FIFO 边界。
3. 为每个级别加入超时、错误计数、唯一 `TEST PASS` 和非零失败退出。
4. O2-D2/O3/O4 锁定后再接入综合后、PNR 功能和 PNR 时序网表/SDF。

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
- S2-A 项目资产位于 `tb/tb_pcie_dma_test.sv`、`tb/pcie_test_smoke_model.sv`、`sim/behav.f` 和 `scripts/run_behav.do`；静态门禁为 `scripts/check_sim.ps1`。
- S2-B 项目资产位于 `tb/tb_pcie_dma_link.sv`、`sim/link.f`、`sim/link_vendor_local.f`、`scripts/compile_vendor_link.do` 和 `scripts/run_link.do`；静态门禁为 `scripts/check_link_sim.ps1`。

### 缺口与风险

- 示例 TB 针对 `pango_pcie_top` RC/EP，不实例化项目 `pcie_dma_test`，不能证明 DMA、RAM/FIFO 和 UART 管理路径。
- `pango_pcie_top_sim.do` 含大量历史绝对路径，filelist 与工作目录耦合。
- S2-A 受控模型只验证项目顶层外壳、复位链和 LED 域；其 link indication 不是真实 LTSSM、TLP、DMA 或板级链路证据。
- S2-B 已参数化厂商加密模型并以 `pango_pcie_top_sim` 为 RC；当前只完成静态合同，尚无动态 LTSSM/link-up 日志。S2-C 再增加基础 DMA 回读。
- 活动 PCIe IP、PDS 目标和新构建产物均与实际 PG2L50H 一致；lane/refclk/PERST#/SCBV 和 UART 决策继续由 H2-B1 阻断。

### TODO（S2）

1. S2-A 静态入口已完成；S0-1 恢复后先运行受控边界 smoke，确认同一 run marker 和唯一 `TEST PASS`。
2. S2-B 静态入口已完成；S2-A 动态通过后运行厂商 RC/项目 EP，覆盖真实 LTSSM/link-up、32 周期稳定窗口和 watchdog。
3. S2-C 在真实链路上增加一次可预测 DMA 写读回；LTSSM、完成状态、数据和超时失败均 `$fatal`。
4. 对应项目网表/SDF 锁定且 H2-B1 关闭后，完成综合后、PNR 功能和 PNR 时序仿真。

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
S0-1 仿真器安装与 USIM/VSIM 编译
        ├─ S1 DDR3：D3-A → D3-B → D3-C → D4
        ├─ S2 PCIe：S2-A 动态 → S2-B 动态 → S2-C → 后级网表仿真
        └─ S3 OV7725：输入格式确认 → O2-D2/O3 锁定 → 集成 TB → 四级仿真
```

在 S0-1 完成前只做静态脚本、filelist 和 testbench 评审，不声称动态仿真通过。厂商示例保留为参考证据；所有项目验收必须由项目自有顶层和自检 TB 完成。
