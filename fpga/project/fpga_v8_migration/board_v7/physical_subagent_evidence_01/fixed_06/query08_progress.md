# fixed06 原生对象查询进度

当前 fixed06 综合失败。`synthesize_result.json` 的 shell exit 0 不构成通过：日志有约束错误且没有 Synthesize done。不得以现有 synthesis DB 为新综合结果。

已完成的 `native_probe_07/compile_dump.v` 以 endmodule 结束。实际 compile 对象包括 `bmsWIDEDFFCPE` 的 `\mailbox[31:0]`、`\mailbox[55:32]` 等分段向量实例，以及 `\host_bank[511:0]`；四个 generate 实例原生 literal 名为 `\cameras[0].source` 至 `\cameras[3].source`。

失败 FDC 位于 `source_diagnostics_route_02/physical_constraints/clock.fdc`，采用综合后逐位名字，例如 `source_diagnostics.cameras[0].source.mailbox[0]/CLK`。compile 向量对象与 synthesis 逐位对象属于不同阶段；仅替换 slash/dot 尚不能解决此差异。完整 FDC pin 名、返回类型和实际集合计数仍须以 importer 输出确认。

`run_query_epoch08.py` 已后台启动，等待原 exporter 完成并留下 input_hashes.json；随后确认 PDS/TA/de 空闲、复核 1022 保护文件，再创建独立 query_epoch08 工程运行真实 synthesize 约束加载。查询带 intentional error，属于诊断失败，不是综合/map/bit 验收。

修正了独立工程准备脚本：除 `_file` 外，`_ip` 和 `_ip_source_item` 也转为原始副本的绝对路径，检查输入存在。所有既有失败目录保留，原始工程与约束不修改。尚未运行新的 map/pnr，bit 门槛开放。
