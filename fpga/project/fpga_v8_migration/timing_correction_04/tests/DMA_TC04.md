# TC04 DMA 隔离候选

候选：`../rtl/axi_dma_write_tc04.v`；参考是实际 V5
`whole_candidate_v5_route_01/rtl/axi_dma_write_tc02.v`，不是生产版或重新生成的 TC02。
模块名独立，参数和公共端口保持原接口。仅 watchdog 更新表达式改为逐位
XOR/前缀进位和 D 路径 clear，其余 RTL token 与 V5 相同。

```powershell
python project/fpga_v8_migration/timing_correction_04/tests/run_dma_tc04.py
```

所有生成 TB、ModelSim work、日志和收据均在 `receipts/dma`。
runner 导入 TC02 的执行函数，并通过 AST 复用其端口解析与 80 场景构造段，
绝不执行原 `main()`：该入口会重建 TC02 候选并写旧 `dma_artifacts`。
TC04 候选是已写好的 patch 文件，runner 只读它。

原有 WAIT=0/1 各 80 场景保留原刺激、长度边界、400 周期随机背压和第 200
周期 abort，改用实际 V5 作参考，并增加 watchdog 状态比较。
新增 WAIT=0/1 × WD_LIMIT=0/1/7/0xFFFFFF，共 8 组：

- 全部公共输出每拍比较，包含 invalid 周期数据、AXI、last 和 abort。
- 1024 种输入/控制组合 × waiting、active burst、stalled AW、waiting B
  四种状态 × WD_LIMIT/饱和值，检查 credits 增减、归零 flush、valid、
  W/AW/B 背压、reset、abort 和同时事件。
- 所有 24 位进位边界、0xFFFFFE→0xFFFFFF、饱和保持，以及 LIMIT−1/LIMIT
  边界使用成对内部状态 deposit；之后在真实时钟沿比较更新。
- 小 LIMIT 自然触发等待源 timeout、已接受 burst timeout、AW stall 时 abort；
  检查 AW 持续有效、dummy W 零 strobe、末 W 前无 BREADY、真实 B 前不退休，
  以及失败退休的 abort/last 脉冲。
- 每组再跑 32 个命令的多周期随机 credits、背压、reset/abort/B error。
  独立 watchdog/abort 边沿 oracle 校验两边，不仅比较候选和参考。

watchdog 仍为 24 位饱和计数；credits progress 同拍判定，没有寄存比较结果。
`!burst_trans` 只位于非 waiting_source 分支。abort 逻辑完全保留，因此在
旧计数已经等于 WD_LIMIT 的边沿，即使 credits 同时变化，waiting-source
timeout 仍按 V5 的旧状态触发；不能擅自改成 progress 取消该 timeout。

收据 `results.json` 给出结果与 SHA；`protected_sha256.json` 保存生产/V5/
TC02/TC03 和本目录其他候选/runner/既有收据的快照；`artifact_sha256.json`
记录候选、参考、runner、依赖、TB 与日志 SHA。非 watchdog token 等价与模块
重名扫描也由 runner 校验。

并行 cam6 任务可能更新自身的 `transcript` 和 `work_registers` 运行数据库。
runner 单独列出这些外部运行期 SHA 变化及已观察到的同一任务
`tests/cam6` 自身 runner/说明修改，保存前后 SHA；若存在则不会宣称所有受保护
文件完全不变。其余文件变化仍使审计失败。本 runner 的全部写目标仍限制在
DMA 收据目录。

局限：没有启动 PDS，没有更改项目绑定。此证据只能证明已覆盖场景的 RTL
逐拍等价，不能证明最终映射不再用 RS 或 routed slack 改善。高位进位/饱和
用状态 deposit 加速，没有等待 2^24 个自然周期；未做形式等价或完整 X/Z
输入空间验证。
