# CI-8A PCIe PDS 构建证据绑定契约

当前平台基线：`RK3568_MES2L100H / PG2L100H-6IFBG484`。旧 50H manifest、日志和产物均不可复用于当前平台。

## 状态与范围

CI-8A 曾在旧 PG2L50H 工程完成试点。该结果只证明 provenance 机制能够拒绝 partial/failed PDS 运行复用旧 full-build 日志和产物，不构成当前 PG2L100H 构建证据，也不关闭 H2-B1 的 lane、refclk、PERST#、UART、SCBV 或 I/O timing 阻断。

固定 manifest 位于：

```text
build/provenance/pds-build.json
```

该文件属于 `build/` 生成物，不提交版本库。工程使用固定 `build/pds` 工作目录，因此契约采用单构建者模型；同一项目不得并发启动两个 PDS build。

## 运行状态

每次 `run.ps1 -Action build` 先生成 32 位小写十六进制 `run_id`，再原子替换旧 manifest：

| 状态 | `valid` | 含义 | `check-build` |
|---|---:|---|---|
| `running` | `false` | 本次运行已开始，旧 complete 证据立即失效 | 拒绝 |
| `partial` | `false` | PDS 成功停在 `gen_bit_stream` 之前 | 拒绝 |
| `failed` | `false` | 输入检查、工具启动、PDS 退出码、`E:` 或证据发布失败 | 拒绝 |
| `complete` | `true` | 本次 `gen_bit_stream` 完整成功且证据已绑定 | 继续执行 H2-B0/strict gate |

`build.tcl` 必须从 `PDS_RUN_ID` 读取同一个标识，并在日志中各输出一次：

```text
INFO: PDS_RUN_ID=<run_id>
INFO: PDS_RUN_COMPLETE=<run_id>
```

缺失、重复或与 manifest 不一致均失败。新鲜度不使用文件时间戳或宽松时间窗口判断。

## 输入与证据

`scripts/pds_sources.f` 是 Tcl 与 PowerShell 共用的 37 个 HDL 单一清单。manifest 固定 43 项 canonical 输入：

- `run.ps1`、`build.tcl`、`build_provenance.ps1`、`pds_sources.f`；
- 清单中的 37 个 HDL；
- `ipcore/pcie_test/pcie_test.idf`；
- `fdc/pcie_dma_test.fdc`。

PDS 前后会重新计算输入记录；构建期间任一路径、长度或 SHA-256 漂移均失败。manifest 固定七项最终证据：

- `build/logs/pds-gen_bit_stream.log`；
- 最终 timing report；
- post-PNR Verilog 网表；
- slow-corner SDF；
- `.sbit`；
- `.bin`；
- `generate_bitstream/bgr.db`。

所有 manifest 路径均为工程相对 POSIX 路径，长度和 SHA-256 直接针对文件原始字节计算。`check_build.ps1` 不提供 manifest、日志、IDF 或产物路径覆盖参数。

## 验证结果

已完成以下动态验证：

- 真实 `compile` partial run 返回 0，manifest 为 `partial/false`，baseline gate 返回 1；
- PDS executable 缺失返回 1，manifest 为 `failed/false`，baseline gate 返回 1；
- manifest run-id、`bgr.db` 字节和 FDC 输入三类漂移均使 baseline gate 返回 1；
- 历史 PG2L50H 七阶段构建返回 0，manifest 为 `complete/true`，包含 43 项输入和 7 项证据；当前 PG2L100H 必须重新生成 manifest、日志和产物；
- H2-B0 baseline gate 返回 0，仍精确匹配 16 个签名、42 次记录并输出不可发布；
- strict gate 返回 1，最差解析 slack 为 `0.100 ns`，五类 H2-B1 阻断保持可见。

## 后续迁移

CI-8B 分别为 DDR3 和 OV7725 HDMI 实现同一事实模型：启动即失效旧证据、完整运行身份、canonical 输入哈希、最终证据哈希、partial/failed 硬拒绝。两个项目的源清单和产物布局必须各自审计；PCIe 试点未证明可以直接抽公共模块。
