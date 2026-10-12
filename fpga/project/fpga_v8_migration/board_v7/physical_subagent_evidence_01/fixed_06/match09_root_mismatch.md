# fixed06 root mismatch 的实际加载证据

源失败文件：`source_diagnostics_route_02/physical_constraints/clock.fdc` 的 mailbox maxdelay/hold 约束引用 `source_diagnostics.cameras[0].source.mailbox[0]/CLK` 等 synthesis 标量实例。实际 pre-synthesis compile DB 的实例是 `source_diagnostics/cameras[0].source/mailbox[31:0]`，host 实例是 `host_bank[511:0]`，且其捕获输入为 `D[0]` 至 `D[511]`，不存在单独的 `D`。

真实 importer 试验文件 `match_epoch09/clock.fdc`：

* 第88、90行：vector CLK 对不带下标的 vector D，均明确 to_list 为空。
* 第92、94、100行：scalar mailbox[0]/CLK 在 compile 阶段，均明确 from_list 为空。
* 第98行：`get_pins -hierarchical {source_diagnostics.cameras[0].source.mailbox[31:0]/CLK}` 对 `get_pins -hierarchical {source_diagnostics.cameras[0].source.host_bank[511:0]/D[0]}` 实际语义加载没有错误。
* 第102行：相同 vector CLK、D[0] 对象用显式 `-hsc /` 和 slash 层次，实际语义加载也没有错误。

因此 compile 表达的具体修正是 mailbox 向量实例 CLK 与 host 向量实例 indexed D。生成块 `cameras[0].source` 是 literal 实例名。现有证据并未隔离证明 -hierarchical 是成功所必需，因为A/B也同时使用了错误的无下标D。不得将主因归结为 slash/dot，也不得把这次无错误加载等同完整对象计数、继承或路径覆盖通过。

query08 实测 get_pins 返回 Tcl 命令表达式而非可计数集合，llength3/4不能用作对象guard。match09 最后 intentional error，验收状态始终false，完整失败保留。

native08 联合向量/标量约束后的真实新综合为1320实际对，仍需按阶段检查全部实际路径。当前另一个控制器 resume_exact09.py 正在真实 dev_map，采用1280 canonical classes加40额外实体等价证明、1320实体全覆盖。该方案不等于1280实际对门槛通过。不得改正在运行的文件。

已准备 synthesis_epoch10 独立拓扑对照工程，完全不加载 mailbox compile实例约束；它要求实际新综合 started/done、导出/解析、1280实体对及748/748/755/755补集全部成立。首次因已活动 exact09 PDS而被单实例guard拒绝；已后台安排仅在其父控制器47848自然退出之后串行执行，仍会检查全局空闲及1022保护文件。该对照不自动启动map/pnr或bit。
