# native08 实际实现与拓扑门槛

`physical_fixed_native_08/dev_map_result.json` 确认实际 Compile、Synthesize、Device Map started/done，综合和 map 均有 successfully，errors 为空。此前查询失败和 fixed06 失败仍独立保留。

真实新综合导出后，manifest 的 errors 为空，2048 个逻辑位均已解析。每路仍有 330 个寄存器逻辑位、182 个恒零逻辑位，但新的唯一物理对为每路 330（共1320），不是此前每路320（共1280）。因此 finish_native08 在 derive_exact_complement 的 len(pairs)==320 断言退出，PNR 尚未启动。

`physical_fixed_native_08/topology_delta09.json` 保存完整逐位差异：每路位 480、490、494、497、498、502、504、505、508、510 此前都合并到 mailbox[240]/host_bank[240]，现在各有同名独立 mailbox/host_bank 寄存器。其他逻辑位映射一致，共40个改变。显式 compile向量约束可能阻止合并，原因还需要受控阶段约束试验验证，不能只按1320放宽断言。

当前联合 compile/synthesis 集合只包含旧320标量启动点及compile向量名，不能证明新增加的40个独立标量路径在 mapped 阶段全部受 maxdelay15.238 保护。需要按实际新图重建阶段约束或采用不会改变合并的阶段加载方式，再真实验证覆盖及补集。

match09 首次及等待后启动都被单实例 guard 拒绝，未启动并发 PDS。确认全空闲后已再次启动独立 match09；该试验仅验证名字解析并 intentional stop，不作为新综合或 map/pnr 验收。原保护、生产/IP 不修改，bit 保持禁止。
