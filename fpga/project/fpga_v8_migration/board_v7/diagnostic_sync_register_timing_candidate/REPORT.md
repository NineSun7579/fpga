# 独立同步/复位寄存器物理签核候选

已在此目录完成两个同接口候选及真实 ModelSim 原版/候选并排比较。推荐下一次隔离映射实验使用 `rtl_primitive/` 两个文件；`rtl/` 保留有官方依据的属性候选作为对照。两组均保持28 sync + 32 reset的逻辑拓扑和全部mailbox/request/ack时序。**物理禁止打包尚未验证，不能宣称原route03问题已修复。**

本次未启动PDS，未改任何现有工程、旧RTL或IP，未进行远程操作或设备编程。原文件按字节冻结于 `baseline/`，SHA256在 `evidence/frozen_inputs.json`、`structural_audit.json`；两组完整diff在 `evidence/`。两组使用原模块名，属于替换文件：后续隔离工程只能选一组，不能把baseline/两组candidate同时加入源表。

## 官方支持与其边界

以下均为本机PDS 2022.2-SP6.4安装包内容；印刷页与PDF页分别列出，摘录保存在 `docs/`。

| 文件 | 印刷页 / PDF页 | 核实的内容 |
|---|---|---|
| `C:/pango/PDS_2022.2-SP6.4/doc/ADS_Synthesis_User_Guide.pdf` | 52 / 53 | HDL支持 `(* AttributeName = AttributeValue *)`；syn_keep/syn_preserve应放在HDL中 |
| 同上 | 53 / 54 | `syn_allow_retiming=0` 禁止寄存器retiming |
| 同上 | 83–84 / 84–85 | `syn_keep=1` 保留实际连接的net，插入keepbuf |
| 同上 | 91–93 / 92–94 | `syn_preserve=1` 保留sequential register；示例是两组同输入寄存器 |
| 同上 | 103–104 / 104–105 | `syn_srlstyle="registers"` 指定inferred shift register映射为Registers；对象含module/instance/register |
| `C:/pango/PDS_2022.2-SP6.4/syn/doc/fpga_attribute_reference.pdf` | 86–88 / 90–92 | `syn_keep` 可设置在寄存器输入wire；页88明确说明保留各寄存器输入网络可防止duplicate registered outputs共享 |
| 同上 | 123 / 127 | `syn_preserve` 作用与支持对象；不能据此推断任何未知实例属性 |
| 同上 | 157–159 / 161–163 | Logos2/Titan2的 `syn_srlstyle="registers"` 与block_ram/lut_ram选择 |
| `C:/pango/PDS_2022.2-SP6.4/doc/Pango_Design_Suite_User_Guide.pdf` | 106 / 107、249 / 250 | `Remove Duplicated Logic` / `-devmap_remove_dups` 是device-map重复逻辑合并开关；默认0 |

已有真实帮助 `../physical_subagent_evidence_01/fixed_06/stage_api12/shell.log` 确认 `-devmap_remove_dups`、`-devmap_const_prop`、`-devmap_control_set_num` 类型均为 `integer_number`，不是TRUE/FALSE。已复制到 `docs/stored_stage_api12_shell.log`。后续隔离实验设置这三项为0的交接记录在 `mapping_handoff.json`；此次没有执行这些命令。

关键区别：文档的syn_srlstyle证明了综合阶段的Registers/RAM实现选择，**没有证明它能禁止后级 `gopSRL2_Cell_*` 两触发器物理打包**。旧证据的SRL2含 `FF0_*`、`FFAPP0_*`，同一个物理cell的内部级没有独立外部D/RS签核端点。不能把Registers映射等同于所有级有独立物理端点。

旧绑定证据实际路径为 `../physical_subagent_evidence_01/fixed_06/physical_exact_11/physical_target_bindings.json`；对应route SHA256 `b0700dc056eccfb31eeaa66793fd6e13789e03f478670109674f41f2524d1a83`。它记录32逻辑reset、20物理RS，req_sync与overrun_sync前两级打包。旧综合导出中的源路径明确指向source_diagnostics_route_03。精简证据在 `evidence/original_mapping_summary.json`，没有把该旧结果当作新candidate的结果。

## 实现

`rtl/`：原syn_preserve/syn_allow_retiming上增加syn_srlstyle="registers"；每级D独立命名并设置syn_keep。仅拆出等价组合别名。`audit.py`去掉属性、还原别名后，两个完整模块的规范化功能体与baseline完全一致。

`rtl_primitive/`：同步ack_sync[1:0]、req_sync[2:0]、overrun_sync[1:0]逐级显式 `GTP_DFF_CE`；cr[1:0]、hr[1:0]和每相机reset_pipe[3:0]逐级显式 `GTP_DFF_PE`。D和Q是有官方支持的syn_keep网络。无新的未知attribute，没有在不受支持的primitive instance上猜测syn_preserve含义。

| 原拓扑 / 每相机 | primitive | 异步输入 | INIT / GRS_EN / CE |
|---|---|---|---|
| ack_sync：2级、cam_clk | GTP_DFF_CE | C=rst_c，置0 | 0 / TRUE / 1 |
| req_sync：3级、host_clk | GTP_DFF_CE | C=rst_h，置0 | 0 / TRUE / 1 |
| overrun_sync：2级、host_clk | GTP_DFF_CE | C=rst_h，置0 | 0 / TRUE / 1 |
| cr：2级、cam_clk | GTP_DFF_PE | P=cam_reset OR host_reset，置1 | 1 / TRUE / 1 |
| hr：2级、host_clk | GTP_DFF_PE | P=cam_reset OR host_reset，置1 | 1 / TRUE / 1 |
| reset_pipe：4级、host_clk | GTP_DFF_PE | P=rst OR cam_reset[g]，置1 | 1 / TRUE / 1 |

四相机共28个CE、32个PE；第一复位级D=0，后级D=前级Q；同步级D逐级与原版完全相同。每级无停顿/门控，原无CE的DFF_C/P使用CE=1的DFF_CE/PE等价。cr/hr为异步置1后两拍释放；reset_pipe为四拍释放。没有把复位置1的级错误替换为异步clear primitive。

真实官方模型路径：

- `C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_DFF_CE.v`：行30–38端口及参数；行49初始化；行52–58依次GRS、异步clear、CE采D。
- 同目录 `GTP_DFF_PE.v`：行30–38端口及参数；行50初始化；行53–59依次GRS、异步set、CE采D。
- 同目录 `GTP_GRS.v`：行79–81定义GRSNET；TB中使用真实GTP_GRS，GRS_N恒1。

`audit_primitive.py`读取旧真实 `physical_exact_11/actual/synthesis_export/synthesis_dump.v`，检查全部60个原GTP触发器的INIT、GRS_EN、复位类型及是否无CE/恒1；28个INIT=0、32个INIT=1全部通过。每个原实例的具体文件/行号、完整参数和连接已保存于 `evidence/original_primitive_stage_extract.txt` 与 `primitive_parameter_audit.json`。初始化不是按模型默认值猜测。

初始化仿真边界：原行为RTL没有initial，未复位的time0值是X；显式primitive依旧硬件参数INIT初始化。此次等价比较从已置起的本地reset之后进行，复位后每周期四态严格比较，GRS_N没有施加额外脉冲。无本地复位的上电行为RTL等价以及全芯片GRS事件不在此次测试结论内；映射INIT已与旧真实综合实例逐级核对。

## 实际ModelSim证据

ModelSim SE-64 10.6e。两组均编译0错误/0警告，仿真0错误；仿真有同一个既有ModelSim配置的novopt性能警告。primitive组直接编译上述安装目录模型，没有自写替代模型。

| 原版并排比较 | 属性组 | 显式primitive组 |
|---|---|---|
| 源模块cam_clk posedge比较 | 2,562,962 | 2,562,962 |
| 源模块host_clk posedge比较 | 1,830,687 | 1,830,687 |
| 异步reset事件比较 | 12 | 12 |
| 原完整帧scoreboard | 2,038检查、0错误 | 2,038检查、0错误 |
| 四相机总线比较事件 | 18,480 | 18,480 |
| 原总线scoreboard | 11,986检查通过 | 11,986检查通过 |

源测试cam/host周期10ns/14ns，总线host/cam周期10ns/14ns。每个时钟沿NBA后2ps严格四态比较全部源outputs；同时比较各同步/复位级、request、ack、mailbox、host_bank及帧计数。总线比较所有17组输出（含legacy master输出），四相机内部28 sync及32 reset逐级比较，含异步短reset事件检查。

覆盖真实cmos_capture与原negedge观测点、640x480完整帧、三种odd segment缺额、边界overlap/相邻帧守恒、空帧、gap饱和、overrun时lease原子性、独立双域reset、四相机all16字段、ACQUIRE/重复ACQUIRE/RELEASE、AW/W三种顺序、B/R背压、短camera reset、epoch失效、已接收读的SLVERR终结及旧地址透明传递。

证据：`evidence/results.json`、`evidence/primitive_results.json`，四个完整TB日志与两组compile日志均在同目录。每组原版同时实例化，原模块仅为避免重复名字机械重命名；原baseline字节内容另存。所有冻结输入SHA256前后核对通过。

## 后续映射签核

此交付已完成实现与本地仿真。后续在PDS空闲时由主session另建隔离工程替换两源，检查compile、synthesize、device-map和routed各层：

1. `evidence/topology_contract.json`列出的28同步级与32复位级各自有独立触发器cell和D/CLK/RS端点；不能只是逻辑名字别名，不能退回gopSRL2内部级。
2. 每级D前驱、时钟极性、CE、复位置位/清零、INIT与GRS_EN与原60级参数证据相同。
3. 保留request三同步级加独立capture edge、原ack返回及mailbox保持合同；继续检查bundled-data max delay。
4. mapped/routed独立验证逐级setup/hold、复位recovery/removal与释放时序。多个独立FF可以共用同一个复位控制net；存储cell/签核端点不得被合并。

显式GTP实例也可能被后级device-map/PNR变换；手册和此次RTL仿真都不是禁止SRL2的物理证明。若仍打包，必须用新映射证据决定下一步，不应直接整合到活动工程或作物理签核通过结论。

复现（本目录，仅本地ModelSim）：`python prepare.py` → `python audit.py` → `python run.py` → `python prepare_primitive.py` → `python audit_primitive.py` → `python run_primitive.py`。不要执行任何PDS流程；两个sim目录各自隔离work library。
