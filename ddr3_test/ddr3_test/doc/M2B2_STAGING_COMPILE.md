# M2-B2：PG2L50H staging compile-only 闭包

## 目标

本批只回答一个问题：由 PDS `2022.2-SP6.4` 重生成的 DDR3 staging，能否在 `Logos2 / PG2L50H / FBG484 / -6` 目标下完成独立 `compile`。

输入固定为 staging 内按厂商工程顺序排列的 18 个 Verilog-2001 示例 RTL，加一个 `ddr3.idf`；顶层固定为 `test_ddr`。该顶层必须保持 26 个端口并包含 `I_ips_ddr_top` 实例。

## 边界

- 每次运行先调用 `scripts/regenerate_ip.ps1`，不复用未知来源的 staging。
- Tcl 只执行 `set_arch`、`add_design` 和 `compile -top_module test_ddr`。
- 不加载 staging 的 FDC/RCF，不执行 synthesize、dev_map、PNR、STA、网表、SDF 或位流生成。
- 不编辑生成 Verilog，不把 staging 升格为 canonical `ip_core/ddr3`。
- PDS work、日志和 TEMP/TMP 使用唯一 run 目录；默认位于项目 `build/`，磁盘受限时可由调用者显式提供仓库外 scratch 根目录。
- 仓库只记录可复现入口和结论，不记录本机 scratch、许可证路径、服务器、feature 或许可证内容。

## 入口

从 DDR3 项目目录执行静态合同与负向自检：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_staging_compile.ps1 `
  -StaticOnly -SelfTest
```

执行动态 compile：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_staging_compile.ps1
```

空间不足时只外置运行态；staging 仍保留在项目 `build/ipgen/pg2l50h`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_staging_compile.ps1 `
  -ScratchRoot '<external-scratch-root>'
```

## 验收合同

1. staging IDF 必须为 PG2L50H、SP6.4，`DEVICE_100H_EN=false`，DDR PHY 使用 `TRUE/CLKOUT4` 分支。
2. 输入必须严格来自 staging：18 个示例 RTL 加一个 IDF；不得混入 canonical 或 backup 路径。
3. PDS 退出码为 0，日志没有 `^E:`，且只出现一个匹配 run-id 的 `M2B2_COMPILE_OK`。
4. `test_ddr_comp.adf`、`test_ddr.cmr` 和 `cmr.db` 必须存在且非零。
5. 四个 canonical 关键输入的 SHA-256 在运行前后必须完全一致。
6. `test_ddr.cmr` 必须恰好记录 18 个 staging RTL 和一个 staging IDF，不能混入 canonical 或 backup 输入。
7. 不得生成综合网表、PNR 网表、SDF 或位流，并重新统计本次 PG2L50H warning。
8. 日志中的许可证 checkout 路径、服务器和 feature 必须脱敏；Git 中不得保存许可证配置。
9. 静态负向自检必须拒绝错误 PG2L100H 目标和 canonical 源路径。

## 当前结果

最终 fresh run：

```text
run_id          1d4b8c264ba940f0bb0e2517b8c36c07
target          Logos2 / PG2L50H / FBG484 / -6
top             test_ddr
inputs          18 个 staging RTL + 1 个 staging IDF
ports           26
PDS exit        0
errors/warnings 0 / 272
PASS marker     1
```

三个核心产物均非零：

| 产物 | 字节数 | SHA-256 |
|---|---:|---|
| `test_ddr_comp.adf` | 1,681,281 | `1D977CA80EFD12581DA762C2A8154506BD7F20DAEAA3E8DADF3018DB5576BF76` |
| `test_ddr.cmr` | 4,684 | `60304183D415E56760825A30E020EAD9A57E6F51D59A79DD5F7E3EF938806F93` |
| `cmr.db` | 286,704 | `7966742C82620D31266D1F180E0B97CA276248CE6F756EE3A46CA4CD0D7E8ED7` |

`test_ddr.cmr` 精确记录 19 项 staging 输入；四个 canonical 关键输入哈希前后一致，5 份运行日志均无未脱敏许可证 checkout 详情。272 条 warning 中包含既有的 2 条 `err_data_pre/err_data_aft` 16→128 bit 宽度不匹配；本批只登记，不把它们写成已修复。

动态负向测试已确认错误目标、零长度核心产物和日志注入 `E:` 均被 gate 拒绝，三项退出码均为 1。静态负向自检同时拒绝 PG2L100H Tcl 和 canonical 源路径。

## 不能证明的事项

M2-B2 不能证明实际板卡 DDR3 颗粒、容量、组织、速率、byte lane、VCCIO、VREF、ODT、终端、refclk、复位或管脚正确；不能证明 staging FDC/RCF、综合、PNR、STA、SDF、位流、初始化、训练、读写 BIST、Questa 仿真或实板功能通过，也不授权 canonical 升格和烧录。
