# route06 IO BANK 报告偏差审查（2026-10-07）

## 结论

`functional_route06` 十组双角时序全部通过（Setup Slow +0.079 ns / Hold Slow +0.141 ns，其余全正），2640/2640 crossing 记录完整，motion32 与 HSST5 保留通过。唯一失败项是原生 IO 报告的完整比对：路由约束迭代后，已占用 IO 的 BANK 列全部显示 BANKL6。

## 该列是报告损坏，不是配置变化——四条独立证据

1. **物理不可能**：112 个占用 IO 中包含封装右侧管脚（`mem_dq[0]`@P6=DIFFIO_R4、`free_clk`@V4=DIFFIO_R5），右侧 pad 不可能属于左侧 BANKL6。
2. **厂商 BSDL 交叉验证**：`PG2L100H_FBG484.bsm` 的 pin→pad→bank 物理映射（285 项）对 112 个端口逐一核对，与合格 V7 基线 BANK 100% 一致，零例外。
3. **同表自相矛盾**：`.prt` 管脚报告中 `cmos1_data[0]` 行的 pad 名 `DIFFIO_L5_G2_12P`（L5）与 BANK 列（L6）同行冲突；pin/site/pad 名与基线零差异。
4. **电气字段零差异**：prr.db IO 表除 BANK 外的全部 21 列（VCCIO/IOSTANDARD/DRIVE/SLEW/终端/IO_REGISTER 等）与基线完全一致。

## 触发因子对照实验

同一 MAP 输入（哈希绑定）：
- route04：`-max_hold_violated_paths_num 30000`（无路由约束迭代）→ IO 表与基线**逐字节一致**，但时序失败（Setup −0.130）。
- route05/06：追加 `-enable_route_constraint_iterate -route_constraint_iterate_times 3`（时序全过的必要条件）→ BANK 列损坏。
- route06 迭代前中间检查 BANK 正常，迭代完成后损坏——损坏精确出现于迭代流程。

结论：`-enable_route_constraint_iterate`（PDS 2022.2-SP6.4）在迭代后重写 IO 报告时损坏 BANK 列元数据；实际 IO 配置（管脚/站点/pad/电气/物理 bank）未变。

## 验收处理

不豁免检查，改为更强的证据验收（`resume_io_verify20.py` / `check_functional_bit10.py`）：
1. BSDL 物理 bank == 基线 BANK（112/112）；
2. 非 BANK 电气字段与基线全等；
3. `.prt` pin/site/pad 与基线全等；
4. fresh BANK 列符合已知损坏特征（全为 BANKL6）；
5. motion32/HSST5 保留通过；
全部满足后，对时序合格的 route06 路由结果执行官方 genbit。偏差记录与哈希保存在 `resume_io_verify20_binding.json`。

历史失败保留：route05 的 `native_IO112_comparison.json` 差异、route04 的时序失败回执均不删除。
