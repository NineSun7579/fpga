# 实际 FDC importer 返回类型与串行状态

`query_epoch08/result.json` 记录了真实 importer 执行：`get_pins -hierarchical *mailbox*` 的 Tcl 返回值为 `get_pins -hierarchical *mailbox*`；`llength` 为 3。加 `-regexp` 后返回四个命令 token，`llength` 为 4。这些数不是 pin 集合大小。不能将本次 SIZE 输出当作实际对象计数或非空匹配证明。

同一上下文 `info commands` 没有 sizeof_collection、get_object_name 或 get_attribute。该上下文支持普通 Tcl，但对象解析被延后；需要实际约束语义加载结果和阶段数据库对象清单交叉验证，不能仅从 Tcl 字符串列表推导匹配成功。

官方 User_Constraint_Editor_User_Guide.pdf 的 PDF 第 69 页（正文 68）说明集成 FDC 的实例层次分隔符为 dot，pin 分隔符为 dot 或 slash；PDF 第 106–107 页列出 get_pins 的 -hierarchical、-hsc、-regexp、-nocase。文档称返回集合，但本版本真实 importer 的 Tcl 返回值是命令表达式，以上实测优先。

match_epoch09 首次启动因已存在 PDS 53016/76680 被 idle guard 拒绝，未创建工程、未启动第二个 PDS。当前活动父 Python 37960 为 run_native_fixed08.py，PDS 正在 standard_flow_fixed_native.pds 执行 dev_map；finish_native08.py（77844）负责后续导出、解析、PNR 和签核。已后台安排等待这两个父进程自然退出后才运行独立 match09 试验，启动前仍有 idle guard。

match09 将分别测 vector/bit、dot/显式 hsc slash、是否 hierarchical，保留每条语义加载错误。其 intentional stop 保证该工程不作为实现验收。

native08 当前显式联合集合由 compile/synthesis 图生成，尚不能替代真实集合计数 guard 或 mapped/routed 覆盖证明。audit_fixed.py 仍须核查新 routed 对象来源、reset32 到24实体及8 camera cr 的豁免检查、完整资源门槛；不能以旧图或空 reset 报告称通过。
