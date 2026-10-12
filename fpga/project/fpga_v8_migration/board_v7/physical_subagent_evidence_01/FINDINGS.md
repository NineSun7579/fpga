# 本机物理流程诊断

本机 PDS 2022.2-SP6.4 build 146967 的 `pds_shell -help` 仅注明 `-run string`，不展开合法枚举。`physical_registered_03/dev_map_shell.log` 是本机实际非法参数 `device_map` 的报错，明确列出合法值：compile、synthesize、dev_map、pnr、report_timing、gen_bit_stream、report_power、gen_netlist。`dev_map` 合法，`device_map` 不合法。

官方 Pango_Design_Suite_User_Guide.pdf PDF 第 166 页（印刷页 165）明确说明 `-run dev_map` 运行到 Device Map，`-run pnr` 运行到 Place & Route。PDF 第 250 页（印刷页 249）将 `-top_module` 列于 compile，不列于 dev_map。

route01 physical_04 已完成且失败：exit_code=1，shell.log 明确出现 `Flow-0182: option top_module is not support for the device` 和 `Actual mapped DB missing`。完整文件已复制至 route01_physical04_failed，归档 SHA256 见 route01_physical04_archive.json。

route02 project.pds 的 compile/synthesize/devmap 均曾标为 `_gci_state 2`，但没有对应 map DB；其 devmap 还含非法 top_module，显式 input_db_file 的格式是 text。不能将这种状态或 exit0 当作已执行证据。

20:56:22 启动的 standard_flow.pds -run dev_map 已在 physical_standard_05/dev_map_shell.log 中出现 `Process "Compile" started.`；这是实际启动的 Compile，尚不能宣称 Device Map 启动。该工程 cmd_devmap 仍有 `(_option top_module (_string "v7_sdt_top"))`，与 physical_04 的实测错误相同。运行期间未修改该工程，也未另外启动 PDS。

旧 whole_candidate_v7_route_01/impl.tcl 的真实成功命令是 compile -top_module ...、synthesize -ads ...、dev_map、pnr ...；旧日志包含 Compile/Synthesize/Device Map/Place & Route 的 started/done 以及 mapped/routed successfully。持久化 DB 为 device_map/<top>_map.adf、place_route/<top>_plc.adf、place_route/<top>_pnr.adf；工程 `_db_output` 的格式是 adif。旧文件只读，哈希证据见 old_v7_evidence.json。

build01_guard.json 的 1022 个文件全部存在且 SHA256 不变，见 build01_protection_check.json。此清单范围之外的生产/旧工程/IP 不应被称为已完整复核；本次未写这些目录。新综合之后必须重新导出 actual graph，复核全部 1280 mailbox 对和 complement，再运行 PNR。Timing4003 为零本身不等价于对象全集正确。
