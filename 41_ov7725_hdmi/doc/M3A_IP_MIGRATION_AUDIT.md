# M3-A：PG2L50H 四 IP 迁移前审计

日期：2026-08-30

## 结论

OV7725 HDMI 工程的 DDR3、PLL、读 FIFO 和写 FIFO 不能通过修改旧 IDF 的器件或版本字段迁移到 PG2L50H。唯一允许进入 M3-B 的路径是：使用 PDS 2022.2-SP6.4 IP Compiler GUI，在目标 `Logos2 / PG2L50H / FBG484 / -6` 下创建当前安装版本的新实例，逐项录入经审核的业务参数，并且只输出到 `41_ov7725_hdmi/build/ipgen/pg2l50h/**`。

本批采用以下硬规则：

- `new-instance only`：不得把 SP4.2 活动 IDF 当作 SP6.4 新实例。
- `staging only`：不得在 `prj/ipcore/**` 或 `prj/ip_backup/**` 原地运行生成器。
- 禁止手改 `<version>`、`<device>` 或隐藏参数伪造兼容。
- 禁止 canonical 升格，直到板级资料、资产差异和 50H 构建证据全部通过审核。
- 旧 PG2L100H STA、SDF、网表、位流、七组失败指纹、endpoint 数和 PLL `+0.192 ns` 只保留为历史证据。

## 范围与边界

M3-A 只完成证据审计和 staging 契约，不修改：

```text
41_ov7725_hdmi/prj/ipcore/**
41_ov7725_hdmi/prj/ip_backup/**
41_ov7725_hdmi/rtl/**
41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc
41_ov7725_hdmi/scripts/build.tcl
41_ov7725_hdmi/scripts/check_build.ps1
41_ov7725_hdmi/scripts/run.ps1
旧 PG2L100H baseline
```

`prj/impl.tcl` 含旧器件和历史绝对路径，只是历史入口，不得用于 M3-B staging 或最终构建。当前 `scripts/build.tcl` 仍以 PG2L100H 为目标，在四个 IP 原子升格前也不得产生面向实板的发布声明。

## 版本断层

四个活动 IDF 均由 PDS 2022.2-SP4.2 build 132111 生成，目标均为 `Logos2 / PG2L100H / FBG484 / -6`。SP6.4 安装定义与活动版本均不一致：

| 实例 | 活动 IP/版本 | SP6.4 安装版本 | 迁移结论 |
|---|---|---|---|
| `ddr3_ip` | Logos2 HMIC_S `1.12` | `1.10` | 必须新建，不得 override |
| `pll_clk` | 28nm PLL `1.3` | `1.5` | 必须新建，不得 override |
| `rd_fifo` | DRM Based FIFO `1.8` | `1.10` | 必须新建，不得 override |
| `wr_fifo` | DRM Based FIFO `1.8` | `1.10` | 必须新建，不得 override |

仓库中的同名历史 backup 是 `Logos / PGL25G / MBG324 / -6`、SP4.2，不是 PG2L50H/SP6.4 seed，也不能复用独立 DDR3 项目的 50H seed。

隔离探针只写入被忽略的 `build/ipgen/**`：

1. 不指定当前安装定义时，四项均报 `IPCompiler 0037`：IP 路径未指定或未安装，退出码 104。
2. 显式绑定 SP6.4 当前定义时，四项均报 `IPCompiler 0057`：活动版本与安装版本不匹配，退出码 104。

因此，旧 IDF 的 CLI override 和手改版本字段均被否决。当前没有找到可验证的新建实例脚本 API；M3-B 使用 SP6.4 IP Compiler GUI 创建新实例，并保存全部参数截图、IDF 和生成日志作为可追溯输入。

## Canonical 哈希保护

M3-A 冻结以下活动 IDF。任何 staging 操作前后都必须复核 SHA-256：

| IDF | SHA-256 |
|---|---|
| `prj/ipcore/ddr3_ip/ddr3_ip.idf` | `4C103420EDF48C5E361A8B7CA132E00EFA268E71B7ABE2BA3826B46A8712E3A1` |
| `prj/ipcore/pll_clk/pll_clk.idf` | `B93FDCB80209C0DA3F0BE9BA08E8D1D9E90D37002473C3BA98E5B3C0AB6EF2A1` |
| `prj/ipcore/rd_fifo/rd_fifo.idf` | `734DAE3B41599127C648E7012C8E7F5D50945A324981AB52ADBD61195BFB049A` |
| `prj/ipcore/wr_fifo/wr_fifo.idf` | `C1C55F4D5C578172B7BA8FBF057163D7E980C9B59C67D99252404A9BDF8E6F70` |

## DDR3 新实例输入

活动配置只能作为业务参数清单，不能作为可生成 seed：

```text
MEM_TYPE=DDR3
DDR_MEM_PART=MT41K128M16XX
MEM_DQ_WIDTH=32
MEM_DQS_WIDTH=4
MEM_DM_WIDTH=4
MEM_ADDR_WIDTH=14
MEM_ROW_WIDTH=14
MEM_COLUMN_WIDTH=10
MEM_BANK_WIDTH=3
DESIRED_RATE=800
ACTUAL_RATE=800
CLKIN_FREQ=50
```

SP6.4 的 `DEVICE_100H_EN` 是隐藏器件派生参数。PG2L50H 新实例必须得到 `DEVICE_100H_EN=false`，不能从活动 100H IDF 的 `true` 继承。

以上 DDR3 参数尚未获板级批准。`MT41K128M16XX` 表示单颗 x16 器件族，而当前 IP 是 32-bit 数据宽度；必须由 BOM 和原理图确认是两颗 x16、其他组织，还是活动配置本身错误。顶层/FDC 当前有 15 位 `mem_a`，活动 IP 为 14 位，row14/row15 也必须由实物决定。

独立 DDR3 工程的 DQ16、DQS2、row15 staging 与本工程的 DQ32、DQS4、row14 配置不等价，禁止交叉复制。

## PLL 新实例输入

当前业务契约是：

| 端口 | 当前用途 | 目标频率 |
|---|---|---:|
| `clkin1` | `sys_clk` | 50 MHz |
| `clkout0` | `pixel_clk` | 65 MHz |
| `clkout1` | `pixel_clk_5x` | 325 MHz |
| `clkout2` | DDR3 `ref_clk` | 50 MHz |
| `lock` | `clk_locked` | 状态输出 |

SP6.4 的 PLL `ui.tcl` 隐藏 `DEVICE_PG2L50H`，并在目标为 PG2L50H 时自动设置为 1。因此新 IDF 必须验证 `DEVICE_PG2L50H=true`，不得沿用活动 100H IDF 的 `false`。

M3-B 只恢复上述现有业务时钟，不同时实施 O2-D2 的控制相位方案。50H baseline 建立后，才重新计算 PLL 相位、generated-clock 对象、STA endpoint 和 O2-D2 是否仍成立。

## FIFO 新实例输入

两个实例都是异步、混宽、异步复位、无输出寄存器：

| 实例 | 写宽/深度指数 | 读宽/深度指数 | 数据方向 |
|---|---|---|---|
| `wr_fifo` | 16 / 14 | 256 / 10 | camera 像素聚合到 DDR 写数据 |
| `rd_fifo` | 256 / 10 | 16 / 14 | DDR 读数据拆分到 pixel 域 |

SP6.4 按 PG2L50H 检查最多 85 个 DRM36K 或 170 个 DRM18K。FIFO 没有与 DDR3/PLL 相同的持久化器件 flag，但新实例仍必须实际通过参数检查，并记录所用 DRM 模式、数量、端口、复位极性、almost-full/empty 阈值和仿真资产。

## M3-B staging 操作

1. 启动 PDS 2022.2-SP6.4，创建或打开只用于 staging 的 PG2L50H 工程。
2. 在 IP Compiler GUI 中分别创建 `ddr3_ip`、`pll_clk`、`rd_fifo`、`wr_fifo` 当前安装版本的新实例。
3. 目标统一选择 `Logos2 / PG2L50H / FBG484 / -6`。
4. 逐项录入本文件中的业务参数；DDR3 板级未决参数不得猜测，未关闭时停止 DDR3 生成与四 IP 原子升格。
5. 输出目录固定为：

```text
41_ov7725_hdmi/build/ipgen/pg2l50h/ddr3_ip
41_ov7725_hdmi/build/ipgen/pg2l50h/pll_clk
41_ov7725_hdmi/build/ipgen/pg2l50h/rd_fifo
41_ov7725_hdmi/build/ipgen/pg2l50h/wr_fifo
```

6. 保存 GUI 参数截图、IDF、wrapper、模板、FDC/RCF、仿真模型/filelist、readme 和完整生成日志。
7. 生成后再次校验四个 canonical IDF 哈希不变。

## 必检差异

四个 staging 实例必须以目录级差异审计，不允许只比较 IDF：

- 顶层模块名、端口名、方向、宽度、复位极性和新增/删除端口。
- DDR3 颗粒组织、地址/数据/DQS/DM 宽度、byte lane、参考时钟、PPLL/CPD、状态输出和校准接口。
- PLL 实际频率、相位、占空比、buffer 类型、lock 语义和 PDS clock object。
- FIFO 宽度/深度、DRM 模式与数量、阈值、读写时钟和 reset/flush 语义。
- 新旧 FDC 的 pin、电气标准、VCCIO/VREF/ODT、时钟和 I/O delay。
- RCF 是否被构建入口显式加载，以及对象是否命中。旧 `ddr3_ip.rcf` 的示例层级与当前 `ov7725_hdmi/u_ddr3_ip` 集成层级不一致，历史日志仅显示处理 0 条 net，不能证明其有效。
- `scripts/build.tcl` 的 16 个手写 RTL、4 个 IDF 和唯一 FDC 输入边界是否仍完整。

## 用户需要审核的板级事实

进入 DDR3 staging 和 canonical 升格前，需要用户依据原理图、BOM 或板厂资料判断：

1. FPGA 实物仍以 `PG2L50H-6IFBG484` 为唯一器件身份，板名中的 `100H` 不参与 `set_arch`。
2. DDR3 完整料号、颗数、容量、x16/x32 组织、row/column/bank、目标速率和 byte lane 映射。
3. DDR3 DQ/DQS/DM/地址/命令/时钟管脚、bank、VCCIO、VREF、ODT 和终端网络。
4. `sys_clk`、reset、OV7725、I2C、TMDS 管脚与电平标准，以及 camera/TMDS 的真实时序要求。
5. `mem_a` 应为 14 位还是 15 位；不得用消除 warning 作为选择依据。
6. 新 wrapper/FDC/RCF/clock object 是否与原理图和实物层级一致。

## 升格和发布闸门

只有以下条件全部满足，才允许把四个 staging 实例作为一个原子批次升格到 `prj/ipcore/**`：

1. 板级审核关闭全部 DDR3 和 I/O 未决项。
2. 四个生成日志退出码为 0，且为 0 error、0 warning 或每条 warning 都有审核结论。
3. IDF 目标和隐藏派生值正确：DDR3 `DEVICE_100H_EN=false`，PLL `DEVICE_PG2L50H=true`。
4. FIFO 资源不超过 PG2L50H 的 85 个 DRM36K/170 个 DRM18K，并且接口契约不漂移。
5. wrapper、FDC、RCF、仿真资产和 clock object 的完整差异已审核，RCF 对象实际命中。
6. 同步更新 build、gate、端口/FDC 契约和 baseline；不保留 100H/50H 混合输入。
7. 从空 `build/` 完成 PG2L50H compile、synthesize、dev_map、PNR、STA、SDF、网表和非零位流，并由严格 gate 验证。
8. ModelSim/QuestaSim 就绪后完成行为级、综合后、PNR 后功能和 PNR 后时序自检，时序仿真确认 SDF 实例层级匹配。

任一条件不满足时，M3 保持阻断。旧 PG2L100H `.sbit`/`.bin` 禁止烧录到实际 PG2L50H 板卡。
