# 紫光盘古100Pro 25 MHz 时钟审计

更新日期：2026-09-02

## 结论摘要

owner 已确认开发板板载晶振为 `25 MHz`。目前只能确认“板上存在 25 MHz 时钟源”，尚不能仅凭该事实推断它直接连接到每个工程的 `sys_clk`、`free_clk` 或 PCIe `ref_clk_p/n`。三类时钟职责不同，必须分别审核。

当前结论：

1. DDR3 原生 `test_ddr` 的 `free_clk` 约束为 40 ns（25 MHz），频率与板载晶振相符；其管脚、电压、`PAP_IO_UNUSED` 和 DDR PHY 参考时钟拓扑仍需原理图/BOM确认。
2. 旧 OV7725 和双 OV5640 参考设计的 `sys_clk` 都按 20 ns（50 MHz）约束；参考 PLL 的 `CLKIN_FREQ` 也是 50 MHz。若 `sys_clk` 直接来自板载 25 MHz，则这两套设计均存在输入频率不匹配，不能直接实现或仿真外推。
3. PCIe 活动工程的 `ref_clk_p/n` 是差分 100 MHz 参考时钟（10 ns），并非板载单端 25 MHz。当前 F6/E6 只是历史候选管脚，必须用紫光盘古100Pro 原理图确认是否接到独立 PCIe 参考时钟。
4. 双 OV5640 参考 FDC 中的两路 `cam_pclk` 25 MHz 是摄像头源同步像素时钟假设，不等于 FPGA 板载晶振，也不应拿来替代 `sys_clk` 或 PCIe refclk。

在板级时钟树、管脚和电气资料闭合前，不修改 canonical PLL/IP、FDC 周期、PCIe refclk 管脚或 generated-clock 声明。

## 逐项目证据

### DDR3

文件：`ddr3_test/ddr3_test/ip_core/ddr_test.fdc`

```text
create_clock -name {ref_clk} [get_ports {free_clk}] -period {40.000}
```

这表示 `free_clk=25 MHz`，与板载晶振频率一致。`test_ddr` 的顶层端口为 `free_clk`，但 FDC 同时标记其候选管脚为 `V4`、`LVCMOS15`、`PAP_IO_UNUSED=TRUE`。因此目前只能说“频率匹配”，不能说“已完成板级连接验证”。

DDR generated clocks 以 `free_clk` 为源，并由 DDR PHY IP 的倍频/分频参数生成；不能用改写输入周期的方式代替重新审核 DDR3 IP、RCF、VREF、bank 电压和走线拓扑。

### OV7725 legacy

文件：`41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`、`41_ov7725_hdmi/prj/ipcore/pll_clk/pll_clk.v`

```text
create_clock -name {sys_clk}  ... -period {20.000}
create_clock -name {cam_pclk} ... -period {40.000}
create_clock -name {ref_clk}  ... -period {20.000}
```

PLL wrapper 的 `CLKIN_FREQ=50.0`。因此该历史工程假设 `sys_clk=50 MHz`，PLL 输出的 `ref_clk=50 MHz`，摄像头 `cam_pclk=25 MHz`。它不是双 OV5640 产品入口；这里只保留为“25 MHz 板载事实与旧 50 MHz 系统时钟假设冲突”的历史证据。

### 双 OV5640 HDMI 参考

参考分支 `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3` 的顶层 `rtl/pcie_video/top_dual_ov5640_pcie.v` 使用 `sys_clk` 驱动 `pll_clk`，并由 `clk_50m` 驱动两路 `ov5640_dri`。其 FDC `constraints/top_dual_ov5640_hdmi_pin.fdc` 为：

```text
create_clock -name {sys_clk}   [get_ports {sys_clk}]   -period {20.000}
create_clock -name {cam_pclk_1} [get_ports cam_pclk_1] -period {40}
create_clock -name {cam_pclk_2} [get_ports cam_pclk_2] -period {40}
```

参考 PLL 的明文 wrapper 仍记录 `CLKIN_FREQ=50.0`；参考审计登记的输出为 75/375/50 MHz。若板上 25 MHz 直接接到 `sys_clk`，保持这些 IP 参数会使 PLL 输入定义与实际输入相差一倍，输出频率也不能按原参考合同成立。正确动作是先确认板上是否存在 25→50 MHz 的时钟芯片/PLL，若不存在，再按冻结的视频模式和 PDS 约束重新生成 PLL，而不是手工编辑厂商生成文件。

### PCIe

文件：`pcie_dma_test_100h/fdc/pcie_dma_test.fdc`、`pcie_dma_test_100h/hdl/pcie_dma_test.v`

```text
create_clock -name {ref_clk} ... -period {10.000}
define_attribute {p:ref_clk_p} {PAP_IO_LOC} {F6}
define_attribute {p:ref_clk_n} {PAP_IO_LOC} {E6}
```

PCIe hard IP 的 `ref_clk_p/n` 是差分 100 MHz 参考时钟；内部 `pclk=250 MHz`、`pclk_div2=125 MHz` 来自 PCIe PHY。当前活动 `pcie_test.idf` 仍是 `PG2L50H`，因此这组时钟证据只能说明接口和约束要求，不能关闭 PG2L100H IP 恢复或实板连接审核。

PCIe 必须单独确认：

- F6/E6 是否连接板上独立 100 MHz PCIe refclk，而不是 25 MHz 晶振；
- refclk 是否由 RK3568 Root Complex、板载时钟芯片或连接器提供；
- P/N 极性、AC 耦合、共模、终端和 PERST# 时序；
- PG2L100H 对应 PCIe IP 的 refclk 规格与当前 FDC 是否一致。

## 必须补充的板级证据

1. 紫光盘古100Pro 原理图中 25 MHz 晶振的器件位号、输出网络、FPGA 管脚和电平。
2. FPGA `sys_clk`/`free_clk` 的实际连接，以及是否经过外部时钟芯片或 FPGA PLL。
3. PCIe 参考时钟的来源、频率、P/N 管脚、走线和与 RK3568 的连接方式。
4. 两只 OV5640 模组的 XCLK/MCLK 来源，以及 `cam_pclk_1/2` 的实际频率、容差和采样边沿。
5. DDR3 reference clock、`free_clk`、VREF 和 bank 电压的原理图/BOM记录。

## 审核后允许的修改

- 若确认 `sys_clk` 直接为 25 MHz：重新生成双 OV5640/OV7725（仅 legacy）所需 PLL，并将 FDC `sys_clk` 改为 40 ns；同步重算所有 generated clock、视频像素时钟、HDMI serializer 和复位时序。
- 若确认存在 25→50 MHz 外部时钟链：保留 50 MHz `sys_clk` 约束，但必须把器件、输出频率、管脚和容差写入板级证据，不能只依赖 RTL 命名。
- 若确认 PCIe 100 MHz 独立差分源：保留 10 ns `ref_clk`，在 PG2L100H IP 重新生成后重新审核 F6/E6 或实际管脚；不得把 25 MHz 约束改到 PCIe refclk。
- 若 DDR3 `free_clk` 确认直接来自 25 MHz 晶振：保留 40 ns 输入约束，并继续审核 DDR3 IP/RCF/电气参数，不因频率匹配而跳过板级验收。

## 当前停止条件

在上述证据未归档前，25 MHz 只能作为板载输入事实，不能作为双 OV5640 `sys_clk`、PCIe `ref_clk` 或任何 PLL 输入参数的批准值。禁止通过修改 `create_clock`、增加 `false_path`/clock group 或手工改写生成 IP 来掩盖频率不匹配。
