# M2-B1：DDR3 器件派生参数与差异审计

审计日期：2026-08-30

## 结论

`DEVICE_100H_EN` 是 Pango DDR3 IP 的隐藏器件派生参数，不是可忽略的历史字段。PDS SP6.4 对 `PG2L100H/PG2L100HX` 设为 `true`，对 `PG2L50H` 必须设为 `false`。仅使用 `ip_generate.exe -device PG2L50H` 覆盖活动 100H IDF 的 header 不会重新计算该参数，会错误生成 100H PPLL 分支，因此该路径已被项目脚本禁止。

当前受支持的自动路径是：先证明历史 SP6.1 50H IDF 与活动配置除 `DEVICE_100H_EN` 外所有参数完全一致，再以它作为参数 seed，交由 SP6.4 build 146967 重新生成全部资产。seed 不是 canonical 输入，也不直接恢复到 `ip_core/ddr3`。

## SP6.4 源码证据

PDS 安装目录：

```text
E:/pango/PDS_2022.2-SP6.4/ip/system_ip/ips2l_hmic_s/
  ips2l_hmic_eval/ips2l_hmic_s
```

`index.xml` 将 `DEVICE_100H_EN` 定义为默认值为 0 的 bool。`ui.tcl` 隐藏该选项，并在 `check_device_100h` 中按器件赋值：

```text
PG2L100H / PG2L100HX -> 1
其他器件（含 PG2L50H） -> 0
```

`ui::check` 会调用 `check_device_100h`，同时重新计算时序、DQS、PLL bandwidth 和其他派生参数。RTL 与 sim_lib 的 `ips2l_ddrphy_slice_top_v1_10_wrapper.v.xml` 使用该值选择 PPLL 分支：

| `DEVICE_100H_EN` | `CLKOUT4_SYN_EN` | `INTERNAL_FB` |
|---|---|---|
| `true` | `FALSE` | `CLKOUTF` |
| `false` | `TRUE` | `CLKOUT4` |

## CLI 覆盖陷阱

以活动 100H IDF 执行 `-device PG2L50H` 时，SP6.4 会把 header 改为 PG2L50H并重新编译模板，但 IDF 中的隐藏参数仍为 `true`，生成的 `rtl/ddrphy/ddr3_slice_top_v1_10.v` 仍是 `FALSE / CLKOUTF`。这证明 CLI 的器件覆盖不是完整的 IP Compiler `ui::check`，不能单独用于跨器件迁移。

项目脚本现在要求：

1. seed header 必须为 `Logos2 / PG2L50H / FBG484 / -6`；
2. 以大小写敏感的参数名和值多重集比较，活动 IDF 与 seed 的参数差异只能有唯一的 `DEVICE_100H_EN`；
3. 活动值必须为 `true`，seed 值必须为 `false`；
4. SP6.4 输出 header 必须为 PG2L50H，生成器必须为 SP6.4；
5. 输出 flag 必须为 `false`，DDR PHY slice 必须使用 `TRUE / CLKOUT4`；
6. canonical IDF SHA-256 在生成前后必须不变。

## 正确重生成结果

使用 SP6.1 50H IDF 作 seed、SP6.4 作生成器，实测：

```text
Exit code       0
Generator       2022.2-SP6.4 build 146967
Target          Logos2 / PG2L50H / FBG484 / -6
Errors/warnings 0 / 0
DEVICE_100H_EN  false
PPLL branch     CLKOUT4_SYN_EN=TRUE, INTERNAL_FB=CLKOUT4
```

参数级比较显示，活动 100H IDF 与 50H seed/正确 SP6.4 输出除 `DEVICE_100H_EN` 外没有其他参数值差异。比较不依赖 XML 参数顺序，并保留仅大小写不同的参数名和重复项。

## RTL 与约束差异

与 canonical 100H 资产比较：

| 资产 | 结果 |
|---|---|
| `ddr3.v` | 内容相同 |
| `ddr3_ddrphy_top.v` | 内容相同 |
| `rtl/ddrphy/ddr3_slice_top_v1_10.v` | PPLL 分支变化 |
| `example_design/rtl/test_ddr.v` | 顶层端口与时钟结构变化 |
| `pnr/ddr_test.fdc` | 时钟、硬宏和 I/O 管脚大幅变化 |
| `pnr/ddr3.rcf` | 内容相同 |
| `sim/modelsim/sim_file_list.f` | 设备相关文件表变化 |
| `ddr3.idf` | header、生成器和隐藏器件参数变化 |

`test_ddr` 端口从 21 个增加到 26 个，没有删除旧端口。新增：

```text
ref_clk_p
ref_clk_n
pll_lock
ddrphy_cpd_lock
ddr_init_done
```

`free_clk` 仍保留。50H FDC 同时建立 20 ns `free_clk` 和 40 ns 差分输入侧 `ref_clk`，DDR PHY generated clocks 改以 `ref_clk_p` 为 source；CPD 位置从 `DDRPHY_CPD_369_466` 改为 `DDRPHY_CPD_297_4`。

FDC 的 `PAP_IO_LOC` 比较共有 28 项差异。除 5 个新增端口外，还包括 `free_clk`、`rst_board`、UART、LED、DDR DQ/DM/DQS 管脚变化。完整 50H pin map 是厂商生成候选，不是实际板卡事实。

## 需要人工审核的板级决策

在提供原理图/BOM 前，以下内容保持阻断：

1. `ref_clk_p/n` 的真实板级来源、频率、引脚和差分标准；
2. `free_clk` 是否确实存在、频率是否为 50 MHz、生成管脚 `W19` 是否匹配板卡；
3. DDR DQ/DM/DQS 重新映射是否与 PCB byte lane 和交换规则一致；
4. `rst_board`、UART、LED 和三个新增状态输出是否接到实际器件引脚；
5. DDR3 颗粒、x16/x32 组织、row/column/bank、VREF、ODT、VCCIO 和终端网络；
6. `DDRPHY_CPD_297_4` 与器件/package 的资源合法性及最终 PNR 结果。

## 升格边界

M2-B1 只完成参数语义和差异审计。只有板级证据逐项确认后，才允许把完整 SP6.4 50H staging 原子升格为 canonical `ip_core/ddr3`，并同步更新 `build.tcl`、`check_build.ps1`、端口契约和约束。禁止只复制 IDF、只替换 FDC、只改 `DEVICE_100H_EN` 或把旧 100H 构建产物继续作为验收证据。
