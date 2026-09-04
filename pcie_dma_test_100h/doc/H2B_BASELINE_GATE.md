# PCIe H2-B0 精确 baseline 指纹门禁

状态：H2-B0 旧 50H 静态指纹仅作历史证据；当前平台为 100H，必须重建指纹。H2-B1 板级闭环仍受外部资料阻断。日期：2026-09-04。

当前平台硬事实：`RK3568_MES2L100H / PG2L100H-6IFBG484`。本文件中的旧 50H 指纹不得作为当前构建或发布依据。

## 1. 目的

`-AllowKnownBaselineIssues` 只用于证明当前失败状态可重复，不能作为发布 waiver。旧门禁只检查五类宽泛正则是否出现，无法发现同类别对象新增、消失、重命名、管脚位置或重复次数漂移，并且可能放行错误的 PCIe IP metadata。

H2-B0 曾将旧 PG2L50H 构建的失败状态固化为机器清单 [`H2B_BASELINE_FINGERPRINT.json`](H2B_BASELINE_FINGERPRINT.json)。该清单在 100H IP/构建重新完成前冻结为历史证据；baseline 模式不得据此放行当前平台。

## 2. 器件硬门禁

以下四元组不属于 baseline 可放行问题：

```text
Logos2 / PG2L100H / FBG484 / -6
```

活动 IDF 任一字段不一致时，无论是否使用 `-AllowKnownBaselineIssues`，门禁均立即失败。构建日志、最终 timing report 和 bitstream database 必须交叉确认 PG2L100H；任何 PG2L50H 痕迹均拒绝。

## 3. 当前精确指纹

| 类别 | 唯一对象 | 原始次数 |
|---|---:|---:|
| `Verilog-2036` UART RX 无驱动 | `rxd -> pcie_dma_test.u_uart2apb_top` | 1 |
| `Timing-4086` 未约束输入 | `button_rst_n`、`perst_n`，各 3 次 | 6 |
| `Timing-4087` 未约束输出 | `pclk_led`、`ref_led`、`txn[0:1]`、`txp[0:1]`，各 3 次 | 18 |
| `ConstraintEditor-4019` serial bus | `rxn`、`rxp`、`txn`、`txp`，各 3 次 | 12 |
| `ConstraintEditor-2002` share pin | `button_rst_n@M15`、`perst_n@M16`，各 2 次 | 4 |
| `Bitstream-2001` | `SCBV` | 1 |

合计 16 个唯一签名、42 条原始记录。阶段重复次数属于当前可重复构建证据；任何签名新增、消失、改名、换 pin 或次数变化均要求重新审核，不能自动更新 JSON。

## 4. 模式语义

严格模式：

```powershell
powershell.exe -ExecutionPolicy Bypass `
    -File .\scripts\check_build.ps1
```

只要五类问题仍有任一签名，返回非零。最终 H2-B1 关闭必须使用此模式。

baseline 模式：

```powershell
powershell.exe -ExecutionPolicy Bypass `
    -File .\scripts\check_build.ps1 `
    -AllowKnownBaselineIssues
```

只有精确匹配 JSON 多重集时返回 0，并输出不可发布警告。baseline 模式不会放行 IP metadata、PG2L100H、负时序、缺失产物或 PDS `E:`。

## 5. H2-B1 仍需审核

H2-B0 完成不证明 PCIe 可上板或可发布。以下项目仍需原理图、BOM、电气资料或产品决策：

1. x2 lane 映射、P/N 极性、连接器方向、AC 耦合与 PCB 拓扑。
2. 100 MHz refclk 来源、F6/E6 连接、终端、共模和容差。
3. `PERST#`、`button_rst_n` 的来源、电平、上电时序及 M15/M16 share-pin 条件。
4. SCBV、配置 bank 电压和启动模式。
5. UART2APB `rxd/txd` 保留或删除；保留时还需管脚、电平与波特率。
6. serial I/O、reset 和 LED 的板级时序约束依据。

不得用宽泛 `false_path`、虚构 I/O delay 或 waiver 代替上述证据。ModelSim/QuestaSim 与 S2 集成仿真是独立阻断。

## 6. 已知后续门禁

当前 `run.ps1` 允许执行 partial stage，而 `check_build.ps1` 读取固定的最终日志和产物；未清理 `build/` 时存在误验旧 full-build 证据的可能。该问题单独进入 CI-8 build provenance/freshness，不在 H2-B0 中用时间戳猜测解决。
