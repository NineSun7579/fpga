# 三项目仿真就绪度矩阵

更新日期：2026-08-30

适用工具：PDS `2022.2-SP6.4`、外部 ModelSim/QuestaSim

## 结论

三项目当前都没有面向项目集成顶层的行为级、综合后、PNR 后功能或 PNR 后时序仿真入口。仓库中发现的 `tb`、`.f` 和 `.do` 主要属于 Pango 厂商 IP 示例，不能直接作为项目验收。S0-1 仍受本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断，因此本矩阵是静态盘点，不代表仿真已通过。

项目级仿真必须新增相对路径的 filelist、DO 脚本和自检 testbench；不得批量修改 `ipcore/`、`ip_core/`、`ip_backup/` 下的厂商生成文件，也不得把厂商示例顶层改名后冒充集成验证。

## 总览

| 项目 | 项目级 TB | 项目级 `.f/.do` | 厂商示例资产 | 当前最高阻断 | 进入动态仿真的前置 |
|---|---:|---:|---|---|---|
| OV7725 HDMI | 无 | 无 | DDR3、PLL、FIFO 示例 | 无摄像头/HDMI 集成 TB；S0-1 | S0-1、输入格式契约、O2-D2/O3 相关 RTL 锁定 |
| DDR3 | 无 | 无 | DDR3 `test_ddr`/memory model 示例 | 旧 TB 端口失配；S0-1 | S0-1、D3-A/B/C 项目自有 BIST/top |
| PCIe DMA | 无 | 无 | `pango_pcie_top` RC/EP 示例 | 示例不实例化 `pcie_dma_test`；S0-1、H2-B | S0-1、PG2L100H IP 一致性、项目级 smoke TB |

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

### 缺口与风险

- 示例 TB 针对 `pango_pcie_top` RC/EP，不实例化项目 `pcie_dma_test`，不能证明 DMA、RAM/FIFO 和 UART 管理路径。
- `pango_pcie_top_sim.do` 含大量历史绝对路径，filelist 与工作目录耦合。
- 没有项目级 `tb_pcie_dma_test.sv`、相对路径 filelist 或四级 DO。
- H2-B 尚未关闭 PG2L50H/PG2L100H IP 元数据冲突、lane/refclk/PERST#/SCBV 证据和 UART 保留/删除决策；在此之前不得把仿真通过写成器件一致性验收。

### TODO（S2）

1. H2-B 资料和 PG2L100H IP 重生成审核完成后，新建 `tb_pcie_dma_test.sv`、项目级 filelist 与行为级 DO。
2. 先覆盖复位、链路建立和 watchdog，再增加一次可预测的 DMA 写读回。
3. 自检 TB 必须对 LTSSM/完成状态、数据一致性和超时使用 `$fatal`，成功只输出一次 `TEST PASS`。
4. 对应项目网表/SDF 锁定后，完成综合后、PNR 功能和 PNR 时序仿真。

## 四级仿真共同门槛

| 级别 | 必须具备 | 失败判定 |
|---|---|---|
| 行为级 | 项目 RTL、相对路径 filelist、集成 TB、USIM | 编译/运行非零、超时、数据错误或无唯一 PASS |
| 综合后 | PDS 综合网表、同一 TB、USIM | 网表编译失败、层级不符或自检失败 |
| PNR 后功能 | PNR 功能网表、USIM+VSIM、同一 TB | 缺少 VSIM 原语、网表编译失败或自检失败 |
| PNR 后时序 | PNR 网表、slow-corner SDF、USIM+VSIM | SDF annotation error、实例匹配错误、未批准 timing violation 或自检失败 |

所有 DO 脚本都必须：从工程根目录启动、建立独立 `build/sim/<level>/work`、写入 `build/logs/`、遇到错误 `quit -code 1 -force`，并在成功路径只允许一个 `TEST PASS`。SDF 层级必须以实际 testbench DUT 实例为准，不能照抄厂商示例层级。

## 依赖顺序

```text
S0-1 仿真器安装与 USIM/VSIM 编译
        ├─ S1 DDR3：D3-A → D3-B → D3-C → D4
        ├─ S2 PCIe：H2-B → 项目级 smoke/DMA TB → 四级仿真
        └─ S3 OV7725：输入格式确认 → O2-D2/O3 锁定 → 集成 TB → 四级仿真
```

在 S0-1 完成前只做静态脚本、filelist 和 testbench 评审，不声称动态仿真通过。厂商示例保留为参考证据；所有项目验收必须由项目自有顶层和自检 TB 完成。
