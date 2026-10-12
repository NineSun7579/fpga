# FPGA 协同加速验证报告

## 验收结论

修复版已完成完整 PDS 构建（All Constraints Met）及 SRAM 烧录，
两组板端短测试通过：完整 RGB 输入逐字节相同，检测结果一致。
240组正式配对全部通过输入字节和检测结果检查：CPU路径25.0570次/秒，
FPGA协同路径20.7620次/秒，吞吐下降17.1410%。功能通过，但当前方案没有加速收益。
下文首次候选的超时和字节错误为历史诊断记录，不代表修复版现状。

## 已完成的板端对照

同一 YOLOv8 模型、同一组 30 个输入，AB/BA/AB/BA 四组配对，
每个配置计时完成 240 次推理：

| 配置 | 完成推理帧率 | 平均完成耗时 |
| --- | ---: | ---: |
| RKNN 浮点输出、原生产解码 | 18.9488 fps | 52.774 ms |
| RKNN 量化输出、兼容解码 | 20.9209 fps | 47.799 ms |

提升 10.4076%，全部检测结果兼容检查通过，计时检测差异为 0。
这是 RK3568 输出与解码优化成绩，不能记为 FPGA 加速成绩。
测试时完整版 detview 仍在运行，没有独占 NPU。
该模型不是当前 detview 默认的 MVP，不能直接用此结果宣称 MVP 提升相同。

## 前处理加速的耗时预算

量化输出配置的平均分段耗时：前处理 3.550 ms、输入提交 1.512 ms、
RKNN 阻塞执行 34.319 ms、输出获取校验 7.967 ms、解码复制 0.409 ms。
前处理约占当前完成耗时的 7.43%。

假设完全去掉 CPU 前处理，FPGA、DMA 和等待成本为零，其他耗时保持不变，
阶段预算推算约 22.60 fps，增幅约 8.02%。这是假设估算，不是 FPGA 实测，
实际协同收益需要计入增加的 DMA 字节、同步与缓冲开销。
此预算使用逐次完成计时平均值；对照 FPS 使用各计时块的总完成数除以总耗时，
后者包含少量块级记账开销，所以两者的耗时分母略有不同。

## 完整 FPGA V8 网络的现有缺口

- 导出器生成的是 HWC16 权重、偏置和 LUT 准备资产，明确不是可执行整网指令。
- 既有上板结果存在 DDR 读回不符、控制寄存器超时和后续传输失败。
- 卷积乘法器存在已定位的流水线延迟问题；隔离修复通过仿真，不等于整网通过。
- 旧引擎在理想 150 MHz 下仅完整卷积工作量估算就至少 105.64 ms；
  直接恢复旧引擎不能证明较 RK3568 加速。推理吞吐上限还需算入其他算子和内存。

所以本次方向为 FPGA RAW RGB565 转 RGB888、模型输入补边等前处理，
RK3568 RKNN 执行网络，不将模型转换为当前旧 FPGA 引擎整网执行。

## 证据与运行身份

- `benchmark.txt`：推理对照和兼容检查结论。
- `pipeline_block_samples.csv`：逐次完成的分段耗时。
- `stage_budget.json`：可复算的阶段预算；生成脚本 `analyze_stage_budget.py`。
- `fpga_acceleration_preflight.txt`：当前主机、驱动、应用和六路状态。
- 现有工作位流 SHA256：
  `fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122`。
- 当前应用 SHA256：
  `73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100`。

本次还重新检查了旧卷积工程 34 个源文件哈希，并使用官方厂商原语模型复验
修复候选的默认四拍乘法流水线：两路各 65,536 个乘积，合计 131,072 个，
输入采样准确、错值 0、X/Z 0、编译及仿真警告 0。
证据：`conv_source_audit.json` 与 `multiplier_validation/result.json`。
这证明隔离乘法器候选的算术和默认流水线对齐，未证明整网执行或板端速度。

## 本次新增的 FPGA 候选

实现位于 `../fpga_acceleration_delivery/ddr_rgb_letterbox/`：
128 位 AXI DDR 读取 RGB565，逐像素转换 RGB888，640×480 补边为 640×640，
写入独立 DDR 输出区，最终写响应完成才发布 done。遇到响应错误停止发布结果。
这是实际 RTL 数据通路，不是 CPU 模拟 FPGA 的性能替代。

八项 ModelSim 测试全部通过，Verilog-2001 编译错误和警告均为 0；
其中两种完整尺寸场景分别核对 2,457,600 个 RGB 字节，与独立 CPU 参考完全一致。
覆盖地址拒绝、读写错误、RLAST 错误、背压、尾部字节和复位恢复。
测试前后核对的 892 个生产源/IP/工程文件哈希保持一致。
证据：候选目录 `artifacts/report.json`、`compile.log` 和各场景日志。

配对主机程序在真实 RK3568 上通过 `-Wall -Wextra -Werror` 的编译和链接，
使用实际 Qt5/RKNN 头文件及运行库，包含实际 ioctl ABI 的 Linux provider；
修复了一处缺失的 `<climits>`。动态库均能解析，无参数启动正确拒绝进入测试。
二进制 SHA256：`6bd751599990daaf777fcfef93afe93db6d6366f53560f6307da38a903ab1d3c`。
尚未打开设备执行 FPGA 推理测试。
证据：`fpga_host_compile.json`、`fpga_host_compile.log`。

候选只支持上述固定尺寸的颜色转换和补边，不支持任意尺寸缩放。
输出数据为 1,228,800 字节，原始 RGB565 为 614,400 字节，PCIe 读回量翻倍。
候选目前采用单拍 DDR 事务，实际传输成本可能抵消前处理收益。
是否加速必须以完整硬件计时为准，不能用仿真周期宣称板端 FPS。

整机候选已经接入 `0x40020000` 控制寄存器、S06 读通路、DDR 写仲裁第七主机，
并加入 cam5 admission hold、排空检查和已发布 bank 保持，供同帧配对使用。
79 个普通 RTL 文件编译通过；真实 crossbar、MMIO 桥、适配器和七主机仲裁仿真
通过，六个竞争相机写主机均有进展；生产 admission hold/resume 仿真通过。
完整顶层和 PCIe 的五个旧文件未通过 ModelSim 普通编译，未计作通过。
完整 PDS 编译/综合/布局布线已成功完成，报告 `All Constraints Met`：
slow DDR/AXI setup 裕量 0.751 ns、PCIe pclk 1.143 ns，fast/slow 检查无失败端点。
报告位于候选工程 `place_route/top_timing_summary_after_hold_fix.txt`。
位流生成成功，SHA256
`b28362e355e705b4456e64057d1c294841b99ac3bf4a401133c23e3ee87abcda`。
已通过 JTAG SRAM 配置 PG2L100H，日志含 done bit=1 和 Program execute successfully。
SPI Flash 保留原 cam5 修复位流，未写入候选。
证据：`candidate_build_manifest.json`、`pds_bitstream.log`、`candidate_jtag/jtag.log`。
最终上板推理结论尚未产生。
首轮 PDS 工程解析发现新 `_file` 缺 `_timespec`，已同时修复生成脚本和孤立工程。

## 板端连接恢复

候选烧录前，RK3568 发生重启，启动 PCIe LTSSM 链路失败，设备未枚举；
直接打开设备的原应用触发旧驱动空设备路径的内核异常。
这些事件发生在候选烧录前，不可归因于候选位流。
随后主机再次启动，通过绑定 `3c0800000.pcie` 到实际 `rk-pcie` 驱动，
恢复 `0002:21:00.0 0755:0755` 枚举、Gen2×2、MSI 和字符设备。
加载驱动 build-id `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a` 与此前保留驱动一致。
证据：`board_reboot_pcie_missing.txt`、`pcie_recovered.txt`、`driver_live_identity.txt`。
本轮硬件验收将在恢复后的 boot `e5e70593-d51c-430a-850e-02a7ee3e917c` 进行。
第一次候选短测试在 MAP 缓冲 ioctl `0xc0045302` 卡住，
`/proc/3077/stack` 显示 `pango_cdev_ioctl+0x40`，未提交加速任务。
解绑 PCIe 并结束测试进程后，驱动仍有引用，无法普通卸载。
已重启 RK3568 建立干净驱动会话；不能将此前测试记为成功完成或性能数字。

干净 boot `21be37d2-a2d5-4f28-9f74-9b6d29e55a55` 中，TX/RX 两个 4 MiB
缓冲成功分配和 mmap，但第一条签名读取超时，日志为
`PCI_DMA_WRITE Error: Timeout waiting for MSI interrupt [g_msi.count=0, g_dma_flag=1]`。
测试进程按 provider 设计停止并保持资源，没有提交 FPGA 前处理命令。
证据：`candidate_mmio_timeout.txt`。MMIO/PCIe 返回链路根因仍在检查，
不能根据超时本身断言 DDR 或前处理算法错误。
已开始将 SRAM 回退到原 cam5 修复位流；SPI Flash 未改动。

回退 JTAG 已成功，恢复完整版 detview（PID 2203）。回退采样六路
have=111111、DMA 错误 0，C5/C6 采集 40.36/40.39 fps，RK3568 NPU 继续推理。
证据：`rollback_jtag/jtag.log`、`rollback_runtime.txt`、`rollback_detview.log`。
回退截图 `rollback_screenshot.png` 中 C5/C6 有明显色彩异常；本次只确认其
计数更新与 DMA 无错误，不能据此称画面颜色已验收正常。该异常原因未定位。

## 控制超时的补充排查

`D:/race/fpga/signature_read_analysis/FINDINGS.md` 记录新增定向仿真：
真实 S00→M02 crossbar、MMIO 适配器和寄存器在 `0x40020000`、
ARLEN=0、ARSIZE=4 下正确返回低 DWORD `0x444c5632`，RID/RLAST 正确，
背压期间数据稳定。实际 DMA 控制器、发送器、读控制器和预取 FIFO 也能
处理 16 字节命令 `0x01000004`，发送签名并产生 MSI 脉冲。

16 字节是一个 128 位 AXI beat；不能将本次超时归因于 MMIO 桥缺少多拍转换。
进一步完成八项连接仿真，加入实际 pcie_fifo CDC、官方 FIFO/RAM 模型、
RX TLP 解码、真实 crossbar/MMIO、DMA 发送器和 MSI 仲裁器。签名响应到
正确 payload 再到 vector-0 grant 均通过；时钟/复位、64位地址、TX 背压和
DDR 对照读取场景也通过。脚本 `D:/race/fpga/signature_read_analysis/repro_complete.py`。
尚未覆盖硬核真实时钟/配置、完整共享 TX 仲裁/credit、物理 TLP 和主机
MSI 交付。当前根因仍未证实，没有据此修改候选 RTL。

下一轮诊断主机程序加入 `DELIVERY_TRACE_DMA` 和 `DELIVERY_DMA_PREFLIGHT`：
日志逐条记录 ioctl/地址/cmd/长度及完成，前置读取普通 DDR `0x00800000`
和现有控制 `0x20000000` 后再读候选签名，任一超时立即停止。程序重新在板端
严格编译/链接通过；此前二进制 SHA256 为首轮版本，诊断版以最新编译 manifest 为准。
正常 viewer 的实际 ioctl 参数从 `/proc` 只读采样，见 `live_viewer_dma_arguments.json`；
该采样不打开 DMA 设备、不暂停应用。viewer 使用 cmd=0；provider 使用 cmd=1，
驱动分支区别正在核实，尚未认定为超时原因。

实际固定驱动二进制审计确认：普通 F2H/H2F 路径不读取 op.cmd，
方向由 ioctl 决定；cmd=0/1 仅在 MAP 选择 TX/RX 时起作用。
两次后续诊断都正常完成 DDR、相机寄存器、候选签名及全部控制 DMA，
此前签名超时未再复现，根因仍未证实，不声称通过修改 cmd 解决。

最新诊断完成 frozen cam5 RAW 614,400 字节读取、前处理 done 和
RGB 1,228,800 字节读取，但与同 RAW 的 CPU 参考不一致，
首个错误在 offset16，共 1,004,213 字节不同。
顶部 153,600 字节中，全部 4,800 个偶数16字节块都是114，
全部 4,800 个奇数块不是全114。这说明需核对真实 DDR 地址/突发契约。
证据 `hardware_mismatch/analysis.json`、三个完整原始数据文件和 `parity_trace.log`。
推理尚未开始，C5/C6 颜色不参与该字节验收；比较的是同一 RAW 的确定性转换结果。

顶层静态审计另发现原 PCIe 完成信号由 TX FIFO 取数计数产生，
不等待最后一拍 AXIS payload 真正被 PCIe 接收。已安排隔离修复和
延迟最后一拍的定向仿真，不能把潜在 MSI 早到直接认定为之前超时原因。

## 修复版实现与短测试

DDR IP 按16位字寻址，top 未转换地址单位；旧单拍候选 +16 步进实际
跨过32个物理字节，造成隔16字节留空。修复 reader/writer 使用与生产
相机及主机一致的16拍突发和256地址步进，保留现有帧存储布局。
详见候选 `DDR_ADDRESS_FIX.md`，12项仿真与六相机竞争集成仿真通过。

F2H 控制器完成条件改为等待请求和真正 TX busy 结束；同时修正两处长度
位宽。八项完整通路测试等待每包最后一拍41周期，覆盖16/256/4352/1228800
字节及32/64位主机地址，全部通过；旧完成条件负对照失败。

修复版位流 SHA256：
`83d4c53e41f7202700a5b31fb75c64a831e52acf56f967f64d50c5a60d38f91e`。
DDR slow setup裕量0.064ns，PCIe pclk裕量1.170ns，最终时序All Constraints Met。
源文件/工程/时序/位流身份 `fixed_build_manifest.json`，烧录证据 `fixed_jtag/jtag.log`。
本次只重建 PCIe 会话，不重启 RK3568 整机。

短测试两组全部字节与检测一致，见 `fixed_smoke.log`、`fixed_smoke.jsonl`。
短测试不足以作性能结论，正式对照为10组预热、240组计时，交替CPU/FPGA执行。

## 最终同模型 CPU/FPGA 对照

| 路径 | 平均完整阶段耗时 | 阶段计时推理吞吐 | P95耗时 |
| --- | ---: | ---: | ---: |
| RAW DMA → CPU RGB/补边 → RKNN/同解码 | 39.909ms | 25.0570次/秒 | 45.113ms |
| FPGA RGB/补边 → RGB DMA → RKNN/同解码 | 48.165ms | 20.7620次/秒 | 56.354ms |

240组、每组同一冻结RAW的两次完成推理，10组预热不计时；包含11个不同
RAW哈希/sequence，重复读取已发布帧也计入，不能称240个不同相机帧。
每组交替前处理及推理次序，两路径使用同一模型/上下文/量化输出/解码。
全部240组RGB字节完全一致，检测结果一致，日志末尾 `pass pairs=240`。

吞吐计算为组数除以各路径测得阶段耗时总和，包含claim、DMA、前处理、
完成推理及release；排除交叉路径字节/检测比较与日志记账。
这是串行独占DMA实验的阶段计时吞吐，不是实时流水线墙钟吞吐或六路显示fps。
viewer在测速期间暂停，和此前18.95/20.92fps共享viewer的软件测速条件不同，
两个实验不能直接跨表比较。

平均耗时：CPU RAW DMA6.507ms＋CPU前处理3.703ms；
FPGA转换、等待与RGB DMA合计18.293ms；RKNN完整调用链两路径
27.437/27.610ms。主要差距在FPGA输入交付链，增加约8.084ms。
当前RGB读回量为RAW的两倍，CPU前处理占比较小，因此当前方案未带来净收益。
不将功能验收通过写成“FPGA加速成功”，也不将RKNN在RK3568的执行写成FPGA整网推理。

证据：`fixed_pairs240.log`、`fixed_pairs240.jsonl`、
`fixed_pairs240_summary.json`、`fixed_stage_means.json`。
报告的FPGA硬件功能由实际控制签名、同帧字节检查、最终完成与检测检查证明；
PDS/仿真只作为补充证据。

## 六路出帧与最终板端状态

修复候选位流下恢复完整应用PID3079，MVP模型，连续12窗口60.722秒：

| 相机 | 采集平均fps | 显示更新平均fps |
| --- | ---: | ---: |
| C1 | 44.99 | 31.39 |
| C2 | 44.98 | 31.16 |
| C3 | 25.73 | 23.83 |
| C4 | 25.73 | 23.73 |
| C5 | 40.39 | 29.22 |
| C6 | 40.39 | 28.84 |

swap平均34.02fps，六路DMA错误0、unstable0、runtime faults空，
MVP调度完成约4次/秒。这是应用显示/调度成绩，与V8独占DMA测速分开。
C5/C6按用户要求只验收持续出帧，不处理颜色。
证据 `fixed_viewer_acceptance/results.json` 及该目录日志。

应用保持运行。SRAM为修复候选83d4…，协同前处理默认不触发，
普通六路显示仍用RAW路径；SPI Flash仍为原cam5修复fcb2…，本轮没有持久烧录。
未做掉电加载测试，未提交或推送本地改动。

已完成可运行的FPGA协同通路和真实开启/关闭对照，但“提高推理帧率”未达成。
完整V8网络仍由RK3568 RKNN执行，FPGA没有完成V8整网迁移。
当前候选适合作为后续优化基线，不能作为已实现性能加速的交付。

回退后约十分钟继续采样，原应用 PID2203 仍运行，六路 have=111111，
DMA 错误全部 0，MVP decode_ok=1，NPU 瞬时 13%。证据 `rollback_followup.txt`。

用户已明确 C5/C6 仅要求持续出帧，颜色不作为本次验收项；颜色排查停止。
此前颜色检查记录：应用 F 键切换六路/HDMI 布局，两种布局都以
RGB565 上传，不能用于更改像素编码。接收侧按低 16 位再高 16 位输出且
不做颜色转换；因此需要同帧 RAW 字节的正常/交换字节解码对比才能确认。
现有计数和 DMA 成功不能证明颜色正确。本次未盲目修改字节序。
回退设备 PCIe 配置确认 MSI Enable+，irq0 持续有中断，AER 错误状态为空；
这只说明回退位流的当前链路可工作，不排除候选签名路径的故障。
