# M2-A：DDR3 PG2L50H IP 重生成

## 目的

本批只建立可审核、可回滚的重生成入口，不直接覆盖 `ip_core/ddr3`。最终硬件目标为 `RK3568+PG2L50H100H` 开发板上的 `PG2L50H-6IFBG484`，PDS 目标为 `Logos2 / PG2L50H / FBG484 / -6`。

## 工具与命令

本机已确认 `E:\pango\PDS_2022.2-SP6.4\bin\ip_generate.exe` 为 `2022.2-SP6.4 build 146967`，支持对现有 IDF 使用 `-family`、`-device`、`-pack` 和 `-speed` 覆盖生成目标。

从 DDR3 项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\regenerate_ip.ps1
```

可指定 PDS 路径或 staging 目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\regenerate_ip.ps1 `
  -PdsBin 'E:\pango\PDS_2022.2-SP6.4\bin' `
  -StagingRoot '.\build\ipgen\pg2l50h'
```

脚本将活动 `ip_core/ddr3` 复制到被 `.gitignore` 忽略的 `build/ipgen/pg2l50h`，在 staging 中运行：

```text
ip_generate.exe -i ddr3.idf -family Logos2 -device PG2L50H -pack FBG484 -speed -6 -log generate.log
```

控制台输出保存为 `build/logs/ipgen-pg2l50h.log`，生成器日志保存在 staging 的 `generate.log`。原 canonical 目录不会被脚本原地修改。

## 当前探测事实

SP6.4 staging 生成已返回退出码 0，IDF metadata 变为：

```text
family    Logos2
device    PG2L50H
package   FBG484
speed     -6
generator 2022.2-SP6.4 build 146967
```

已观察到 `ddr3.v`、`ddr3_ddrphy_top.v` 和 `ddr3.rcf` 与活动基线内容相同，而 `example_design/rtl/test_ddr.v`、`pnr/ddr_test.fdc` 和 IDF 发生变化。50H wrapper 在保留 `free_clk` 的同时新增 `ref_clk_p/ref_clk_n` 与 `GTP_INBUFDS`；FDC 也切换到 50H 专用硬宏和 generated-clock 结构。这些差异必须作为真实迁移输入审查，不能手工删回旧端口。

IDF 中的 `DEVICE_100H_EN` 参数在本次 probe 中仍出现原始值 `true`。它不是 `<header><device>` 字段，不能仅凭该参数值断言生成目标仍为 100H，也不能把它伪造为 `false`。升格前必须由 IP Compiler/器件专家确认其语义及对 50H 生成结果的影响；脚本只记录原值并阻止缺失参数被静默忽略。

## 升格条件

只有同时满足以下条件，staging 才能替换 canonical `ip_core/ddr3`：

1. 实际 DDR3 颗粒、容量、x16/x32 组织、row/column/bank、VREF、ODT、供电和 PCB 管脚已由原理图/BOM 审核确认。
2. `ddr3.idf` 的 header 与 `Logos2 / PG2L50H / FBG484 / -6` 一致，生成器为 SP6.4；`DEVICE_100H_EN` 等配置项的语义已得到明确结论。
3. `test_ddr.v` 的端口、复位链、`I_ips_ddr_top` 层级与 D3-0 端口契约逐项复核；新增的差分 `ref_clk_p/n` 必须同步进入板级证据、输入清单和物理约束，不能误删仍保留的 `free_clk`。
4. 新 FDC/RCF 的 50H 硬宏、I/O 位置和 generated clocks 与实际板卡证据一致。
5. 以新 IP 从空 `build/` 完成 compile、synthesize、dev_map、PNR、timing、netlist 和 bitstream；CI-6 只引用新报告和新产物。
6. 新报告无未分类 critical，时序与端口门禁通过；QuestaSim 可用后再验证四级仿真和 SDF 标注。

## 回退条件

出现以下任一情况，立即保留旧 canonical 目录并删除或隔离 staging，不得通过 baseline、waiver 或手工 XML 修改掩盖：

- IDF metadata、生成器版本或关键资产不符合目标；
- wrapper、端口宽度、`I_ips_ddr_top` 层级、地址单位或 `axi_wready` 语义漂移且未完成 D3-0 复核；
- FDC/RCF 仍含 100H 硬宏，或无法与板级管脚/电压证据对应；
- 从空构建得到的 PDS 日志、STA、网表、SDF 或位流失败；
- 发现 DDR3 物理参数缺失、仿真器不可用或 SDF 层级无法标注。

本文件不授权 D3-A 功能 RTL，不授权烧录；它只完成 M2-A 的重生成入口和审计边界。
