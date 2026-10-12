# 真实综合对象与 STA A/B 实测结果

## 结论

mailbox 绝对最大延迟的约束表达和 Slow 综合路径覆盖已实测有效：独立 `B_exact_grouped.sdc` 覆盖 **1280/1280 个真实寄存器对**，对应全部 **2048 个逻辑位**；每对均明确报告 `MaxDelay Path 15.238ns -datapath_only`、CLK→Q、net、capture setup，data required=15.102 ns，slack=+14.514 ns。敏感性下调到 0.001 ns 后同一路径 slack=-0.723 ns。

**尚未关闭完整物理门槛，不准备或启动 PNR。** 编译日志 `Sdm-2008` 明确 ASYNC_REG 属性不合法、无效并被忽略；成功综合 dump 中该属性出现次数为 0。综合 TA 为 single Slow corner，不能提供 Fast/routed 签核。`-allow_paths` 实际被 TA SDC 解析器忽略，不能采用。

上述数字是综合 estimate，不能当作最终布线延迟、Fast hold 或物理 CDC 签核。

## 输入与隔离

- 唯一 ADIF 输入：`../synthesis_export_02/synthesis_dump.txt`。首次 timeout 导出没有使用。
- 原综合 DB SHA256：`535008933c3cf43b8f80e4187d883cf2a1003684f4c2cb06a8307658ad71c3fc`，最终复核一致。
- `hash_audit.json`：1416 个 protected 文件、740 个 inputs 文件 mismatch 均为 0，含原六份 FDC 指纹。
- 所有新脚本、候选和试验 DB 副本均在本目录。无 production/IP 修改，无 remote/program，无 PNR。
- PDS/TA 串行运行；长启动使用后台无超时，TA 通过 `CloseMainWindow()` 正常关闭，未杀进程。正常 GUI 关闭 exit 1，结果判断依赖实际日志及报告。

## VIEWREF 解析修正

原解析器只取 CELL 的首个 VIEW，导致第 2–4 路相机使用错误专用 VIEW，时钟 driver 缺失。已按实例 VIEWREF 选择 CELL/VIEW，旧结果封存在 `parser_first_view_archive/`，不得作完整映射证据。

修正后的对象：3315 CELL、3555 CELL/VIEW、78201 primitive；四路 PCLK 均追到各自 `cmosN_pclk_ibuf/O`，AXI 追到 `u_sysclk_bufg/CLKOUT`→DDR GPLL。`manifest.json` 有 2048 位、errors=0：1320 位映射至1280真实对（40合并位），728恒零；实际 LUT 读出验证仍通过。28同步寄存器、16普通同步级间对、32逻辑 reset 位、8负沿 binding 均重新分类。

时钟实际为 **20 个声明/生成时钟，19 个有负载**；`clk_150m` 0 loads。此前“19 时钟”的表述漏计这个合法零负载时钟。

## 精确旧 CDC 补集

`derive_exact_complement.py` 验证每个 mailbox primitive 只有 Q 输出，Q net 的唯一输入 sink 是对应 host_bank D。因而在原 Camera→AXI 路径全集 U 中，mailbox 启动点 M 发出的数据路径恰为 B；没有 M→其他终点路径，也没有其他启动点→host_bank D 的数据路径。

因此 U\B 可以由 `(S\M) × AXI capture clock` 表达。S 从真实时钟 net 枚举 DFF/DRM clock pins，追踪 INV/clock buffer/keep buffer，包括负沿寄存器；未识别时钟 sink 数为0。

| Camera | S 实际启动点 | mailbox M | 旧豁免补集 S\M | TA clock loads |
|---|---:|---:|---:|---:|
| 1 |1068|320|748|1068|
| 2 |1068|320|748|1068|
| 3 |1075|320|755|1075|
| 4 |1075|320|755|1075|

原48条生效 timing 命令中43条在派生 timing-only 文件中保留原值/映射后的对象，替换的仅为四个 PCLK 和 ddrphy_sysclk 的5条单组 async。20钟有向关系矩阵确认：只迁移 Camera→AXI 四个有向关系到路径级补集；反向、Camera↔Camera、其他时钟关系保持。原六份 FDC 没有编辑；TA 不支持的物理 define_attribute 未用于 TA timing-only 导入。

`exact_complement.json` 是结构集合，`candidate_validation.json` 是加载及报告后的交叉审计。分组 maxdelay 的 M×H 仅匹配真实1280直连对；没有因集合乘积增加额外路径。补集与 mailbox 启动点无交集，未豁免同步后级、同域普通路径或全 reset 树。

## A/B/C/D 与敏感性

| 实验目录 | 实际结果 |
|---|---|
| `ta_A_one_pair` | 原 async 加 maxdelay/hold；早期查询未显式开启 report_exception，单独不足以严格比较 |
| `ta_A_exception_02` | 原 async 加 maxdelay/hold；显式 report_exception TRUE，命令成功，规范报告 MaxDelay 条数0，定向路径为空 |
| `ta_B_import_02` | 拆分 async +单对 maxdelay +hold-only；required15.102、slack+14.514 |
| `ta_C_options_first` | 明确 GUI 导入后，无新 hold-only；同一单对 required15.102、slack+14.514 |
| `ta_D_import_02` | 四次 `SDC-2005: Option '-allow_paths' is not supported ... ignored`；路径为空 |
| `ta_sensitivity_02` | 单对 maxdelay0.001；required=-0.135，slack=-0.723，约束失败 |
| `ta_B_exact_grouped_01` | 精确补集+四路分组 maxdelay/hold；1280对，missing0、unexpected0 |

B/C 证明新 hold-only 不屏蔽已报告的 setup 最大延迟。两者的跨域单对报告均没有 min 路径，因此不将其冒充 Fast hold 证明。最终分组报告1280条全部为 max/Slow。

最后 A 对照通过 GUI 明确导入原 async 候选；`ta_A_exception_02/shell.log` 记录下列命令 `successfully`，其自有 `v7_sdt_top.snr` 与 `timing_audit.json` 确认 MaxDelay 条数为0。与同对象 B/C 非空报告对照，原 global async 下新增最大延迟未得到可验收路径；A 的“All Constraints Met”不能视为 mailbox 通过。A 只查询单对，因此审计输出的 missing1280 是相对完整集合的诊断数，不是一次全束查询结果。

```tcl
report_timing -report_exception TRUE -from [get_pins {source_diagnostics/cameras[0].source/mailbox[0]/CLK}] -to [get_pins {source_diagnostics/cameras[0].source/host_bank[0]/D}] -max_path 100 -nworst 10
```

先前1280逐对例外导入发生 `0xC0000005`，保留原失败产物。本次用每路集合分组，实际导入与报告成功；不能将新成功抹去此前崩溃记录。

## 实际命令与报告

代表性启动（每个变体新会话/DB 副本）：

```powershell
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/run_ta_gui.py ta_B_exact_grouped_01 B_exact_grouped.sdc
```

其 `launch.json` 保存实际 `ta.exe -sdc <combined.sdc> -rtr <trial> <synthesis.adf>` 命令。**不根据 CLI 参数推断已加载。** 成功实验用 GUI Import DB and SDC 明确填写三项，`ui_import.json` 保存路径，`shell.log` 确认实际执行候选 async、补集、maxdelay 和hold命令。早期 CLI 未加载候选的 B/C 目录仅为加载失败证据。

完整报告实际执行：

```tcl
report_timing -report_exception TRUE \
  -from [get_clocks {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk}] \
  -to [get_clocks {ddrphy_sysclk}] -max_path 2000 -nworst 2
```

规范数据报告为 `ta_B_exact_grouped_01/bundle_max.snr`，不是旧控制器复制默认目录的 `report_snapshot/`。后续查询覆盖工具默认 `v7_sdt_top.snr`，各次已另存 `ordinary.snr`、`negedge.snr`、`reset.snr`。逐位证据在 `bundle_max_audit.json` 与 `timing_audit.json`；不以摘要“0 failing”或报告上限替代覆盖审计。

每条 mailbox 路径：tco0.203 +net0.385 = arrival0.588 ns，max_delay15.238 -setup0.136 = required15.102 ns，slack14.514 ns。未使用异步时钟的默认相位关系计算绝对界限。

验证命令：

```powershell
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/audit_timing_report.py ta_B_exact_grouped_01 bundle_max.snr
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/audit_candidate.py
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/audit_hashes.py
```

## 普通路径、负沿、reset

| 查询 | 实际覆盖/最差 Slow slack |
|---|---|
| 普通同步级间 |16/16对，16 setup +16 hold；+6.417/+0.291 ns；新增例外0 |
| 负沿 binding |8/8启动点；4450 setup +4520 hold；+2.952/+6.576 ns；新增例外0 |
| AXI reset_pipe P |16 recovery +16 removal；+4.372/+2.255 ns；新增例外0 |

负沿报告明确记录 `Clock cmos1_pclk (falling edge) 5.952`→GTP_INV→寄存器上升沿，而 capture 使用后续PCLK边沿。上述条数为实际 query 输出，不能当作物理全设计签核。

32逻辑 reset 位对应24真实寄存器，hr[0:1] 合并到 reset_pipe[0:1]。24个真实 P 目标中的16 AXI reset_pipe 有 recovery/removal 报告；8个 camera cr 的跨域源路径沿用原 AXI→Camera 豁免，不能把空报告视为恢复/移除通过。MPW 的综合Slow摘要不替代复位最小脉宽和Fast检查。

综合 TA 的实际 `report_timing -help` 没有 `-delay_type`/corner选项。传入 `-delay_type min_max` 得到 `Flow-0073`；默认查询仍返回适用的Slow setup/hold/recovery/removal。该失败未覆盖已保存的有效bundle报告。

## 未关闭门槛

1. **ASYNC_REG 实际无效。** `../compile_warnings_review.txt:2480` 起明确 `Sdm-2008`，属性不合法、无效并忽略；候选RTL确有该属性，成功dump出现次数0。没有猜测或追加未经验证的厂商替代属性。
2. **Fast、routed 与完整 reset/MPW 签核未提供。** 当前是综合 single Slow estimate；有效Slow结果不能推导这些检查通过。
3. **allow_paths 不可用。** 帮助/二进制存在文字不等于SDC解析器支持，实测SDC-2005优先作为结论。

因此只关闭“mailbox最大延迟表达、Slow完整对象覆盖、敏感性及结构补集”这部分验证；保持物理门槛OPEN，不准备/启动PNR。所有TA已正常请求关闭，最终无TA/PDS/pds_shell实例。
