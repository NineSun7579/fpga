# PCIe S2-F 负时序求解器诊断

更新日期：2026-09-01

## 目的与边界

本诊断比较 Questa Sim-64 `2021.1` 的 `-glsnegtchk level1/level2/level3`，用于
判断 Pango timing model 告警是否对负时序求解器敏感。三档使用完全相同的 canonical
PNR timing netlist、slow-corner SDF、项目 TB 和仿真库，并始终保留：

```text
+delayed_timing_checks
+ntc_warn
```

诊断不会修改 `run_post_pnr_timing.do` 的 canonical `level2` 验收配置，也不会把
`level1` 或 `level3` 的结果作为签核依据。`level0`、`+no_neg_tchk`、
`+notimingchecks`、`+ntcnotchks`、`+nospecify` 和 timing message 抑制均不进入矩阵。

## 工程入口

版本库归档：

```text
sim/questa/run_post_pnr_timing_diagnostic.do
scripts/run_post_pnr_timing_diagnostic.ps1
scripts/check_post_pnr_timing_diagnostic.ps1
```

启动器为每档创建独立 simulator 进程，因为 TB 的 `$finish` 会结束当前
`vsim.exe`。每档完成后，启动器校验路径并删除该 run 的 ignored work/launcher
目录；日志和汇总 JSON 仍只写入项目 `build/`。

运行命令的工具安装位置通过参数提供，不写入仓库：

```powershell
.\scripts\run_post_pnr_timing_diagnostic.ps1 `
  -QuestaBin <questa-install-root> `
  -PdsRoot <pds-install-root>
```

## 固定输入

最终有效矩阵 run：

```text
f79dc238c12949b7b67db2ef0d0ddd0b
```

Questa 版本：

```text
Questa Sim-64 vsim 2021.1 Simulator 2021.01 Jan 19 2021
```

| 输入 | SHA-256 |
|---|---|
| timing netlist | `5CD3073D4708DA3E0DDA9C27FCA7DD8BE2AF3254D8B9A348B0647DF5750CB601` |
| slow SDF | `B7150A1ACE1A668AE2E11DD36C193D2C56F8B43C92383048A1B380F9D9CC03BA` |
| timing TB | `C3BDBCAA7B5FA8CE6795E78F07A93DB6C72E8EEC41A22F9D1A04668F0AE3C105` |
| `V_FFASYN.v` | `6A12EB54FA7F3B362564B6A7D65E87B06C7E526E0A26DDB1564E72FD7E6DA3` |
| `V_DRM18K_E1.v` | `9F35147248620F5C6FD7DE0077C2EF676DBE791CB283D98186BFAD2350834B43` |

这些哈希只标识本次仓库外模型输入，不授权把厂商安装目录或模型副本提交到 Git。

## 动态结果

三档均满足：进程退出 0、SDF marker 恰好一次、功能 marker 恰好一次、`TEST PASS`
恰好一次、`vsim-3316=0`、`vsim-3616=0`。但 simulator summary 均为
`Errors: 2`；按 `level1/level2/level3` 排列，`vsim-3004=3624/1590/1590`、
`vsim-8756=1/1/1`。所以矩阵完成不等于 S2-F 通过。

| Solver | `vsim-3004` | `vsim-8756` | Setup | Hold | Errors | Warnings | Suppressed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `level1` | 3624 | 1 | 1 | 1 | 2 | 3625 | 340 |
| `level2` | 1590 | 1 | 1 | 1 | 2 | 1591 | 340 |
| `level3` | 1590 | 1 | 1 | 1 | 2 | 1591 | 340 |

精确归因：

- `vsim-3004` 来自 `V_DRM18K_E1` 的负 `$setuphold/$recrem` 求解失败；
- `vsim-8756` 来自 `V_FFASYN` 缺少 delayed reference/data copy；
- 三档的正 setup error 都位于 `CLMA_267_624/FF0/FF`；
- 三档的正 hold error 都位于 `CLMA_267_612/FF0/FF`。

`level1` 比 `level2` 多 2034 个 `vsim-3004`，说明旧 rise/fall 统一延迟求解器对
DRM18K 模型更不利。`level3` 与 `level2` 的统计完全相同；当前设计没有证明需要
conditional solver 的 `COND/&&&` 模型依据，而且 `level3` 放宽了 delayed signal
跨越 reference event 的 LRM 要求，因此只能保留为非 canonical 诊断。

两个正 setup/hold error 在三档中完全不变；对应 SDF cell 的相关限制为正数。这进一步
证明负限制求解器切换不能解释或豁免两个 HSST reset debounce error。

## 结论与关闭条件

```text
DiagnosticCompleted: true
AcceptanceStatus: blocked
CanonicalAcceptanceChanged: false
```

当前没有可审核的运行参数能补齐四实参 timing model 的 delayed reference/data 功能
语义。重新编译同一模型或切换 solver 只能改变告警数量，不能成为签核修复。

S2-F 仍只能由厂商确认与当前 PDS、器件和 Questa 组合兼容的修订模型或书面解释关闭。
取得该输入后，必须回到相同 canonical netlist/SDF、无 force TB 和 `level2` 配置重跑，
并满足 `vsim-3004=0`、`vsim-8756=0`、所有 timing error 为 0、最终
`Errors: 0`、唯一 marker/PASS 和 PowerShell 退出 0。
