# TC03 motion 隔离候选

候选：`../rtl/block_motion_detector_tc03.v`，独立模块名，未绑定生产工程或 V4。

已读取 V4 的完整四条失败路径与全部 TC01 RTL；V4 RTL 与 TC01 字节一致。
起点 `cam3_ov5640_top/u_motion_tap/u_detector/mark_q[134]`，终点
`min_y_work[0..3]/CE`，slack −0.260 ns。数据到达 12.882 ns，要求
12.622 ns；6 级逻辑，逻辑 1.159 ns，布线 6.128 ns（84.095%）。
这说明优化需要考虑归约结构和布线，RTL 层级减少本身不能证明物理时序改善。

改动仅涉及 bbox 更新资格：每行归约连续的 `mark_block`，每列收集并归约
相同列的 `mark_block`。行/列的固定坐标分别与当前 bbox 的 min/max 比较，
将结果同局部标记相与后才作最终归约。四个 bbox 坐标 enable 因而不再经过
全局 `mark_any` 后接动态 `update_by/update_bx` 比较。
`mark_any` 仍用于 changed_blocks 和 bbox_valid，未消除所有全局归约。

等价依据：正常接受的 sample 的 `select_q` 为 one-hot，标记的唯一行、列
分别等于同一 sample 的 `update_by/update_bx`。所以局部资格的最终 OR
等于原来的 `mark_any && (!bbox_work_valid || update_coordinate <或> bound)`。
清空优先级、阈值前递、计数、读优先历史 RAM、结束/发布时序和所有寄存器
流水级保持原有逻辑。单行/单列通过至少 1 位的坐标类型处理。

运行：

```powershell
python project/fpga_v8_migration/timing_correction_03/motion/run_motion.py
```

脚本读取并复用 `timing_correction_01/run_regression.py` 的 motion 生成段，
不导入或运行其写入旧 receipt 的主体。原五几何 oracle 实例化 TC03，
同时逐拍比较全部 11 个公共输出与原版、V4 的精确 TC01 RTL。
随后在隔离目录复用 `run_four_integration.py`，只重定向候选绑定和产物路径。
四路测试为四个 640×480 adapter + motion 寄存器 bank，覆盖 10 个阶段、
短帧恢复、记录原子性、core end+2 / adapter end+3、冻结快照与空槽 4/5。
它不是带厂商 IP 的整机仿真。

每次运行使用新的 `run_时间戳/`，保存完整失败路径、候选 diff、生成 TB、
adapter 绑定、编译/仿真日志、保护文件 SHA256 和新 receipt；不会覆盖旧 receipt。
`results.json` 只有两套真实仿真完成且保护文件 hash 不变才生成 PASS。
保护集包括生产 source 文件、project.pds、V4 RTL、TC01 RTL/runner/receipt、
原 motion TB 和 TC03 相机源码；不对其他会话正在生成的相机仿真产物作 hash 保证。

候选 SHA256：
`9a6ddfc10a385d3b911d05e34b3705f893812a0f3ac6a408ee52745ce737e283`。

已核验本次 paired 编译日志明确列出原版、V4 TC01、TC03 和隔离生成的 TB：
`run_20261006_010920_353402/paired/compile.log`，Errors=0、Warnings=0。
较早的 `run_20261006_010904_306816/` 为 shell 1 秒超时中断的尝试，
不能据此宣称回归通过。功能结果以成功完成运行的 `results.json` 为准。
另以 `vlog -work work`（不带 `-sv`）编译候选 `.v`，
`verilog_syntax/compile.log` 为 Errors=0、Warnings=0；这只是语法检查。

本次真实功能结果：`run_20261006_010920_353402/results.json` 为 PASS，
其 12 项产物 SHA256 已逐项复核，候选 SHA256 再次核验一致。

| 几何 | step | 公共输出逐拍比较周期数（每个参考） | oracle 发布数 |
| --- | --- | --- | --- |
| 1×1 | 1 | 254 | 35 |
| 5×3 | 1 | 680 | 28 |
| 21×13 | 4 | 8,876 | 28 |
| 640×480，整数参数 | 4 | 5,094,402 | 16 |
| 640×480，11 位 packed 参数 | 4 | 5,094,402 | 16 |

合计 10,198,614 个实例周期，每周期全部 11 个公共输出同时与原版及 V4
对比，均无差异。完整帧/历史/literal oracle 全部通过。
四路集成 10 个阶段全部通过，共 3,378,505 周期，包含相机 2 短帧隔离恢复。
两套编译均 Errors=0、Warnings=0；两套仿真均 Errors=0、Warnings=1，
唯一计入的环境警告是继承 `-novopt` 关闭优化导致仿真较慢。
435 个保护文件前后 SHA256 相同，旧 receipt 未覆盖。

成功 receipt SHA256：
`5b6a9a6a08e7f43ad00fd90a1db2052401b9cde3c213653fa98fa10dec226eb4`。
V4 基线 RTL SHA256：
`109a04b0714c3a0cc302686171e4776abe31351ce0ccdd19927c27d1347952ca`。

局限：未启动 PDS，未综合、布局布线或执行候选 STA；没有测量新的 slack、
资源或 Fmax。综合器可能重写或共享局部逻辑，实际收益需后续独立物理实现确认。
