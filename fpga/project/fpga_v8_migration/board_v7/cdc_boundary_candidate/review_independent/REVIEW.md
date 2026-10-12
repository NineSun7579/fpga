# V7 有序 CDC 候选独立审查

结论：**不能直接集成 V7 候选。** 正常契约内的有序像素/marker 机制有仿真支持；实际冻结板级连接不满足联合复位要求，fault 没有接到事务处理路径，新 metadata FIFO 没有物理 CDC/实现验收。不能把这些缺口写成已经可上板的修复，也不能把 source=307199/198/193 解释掉。

本审查只读取本地文件，只新增 `review_independent/`。没有 remote、program、PDS 实现或生产修改，没有改原有测试结果。下文 `C/` 表示本候选目录，`F/` 表示 `project/fpga_v8_migration/whole_candidate_v7_route_01/`。

## 证据绑定

- 本地板端运行收据 `board_v7/run_20261006_141824_27582c99/receipt.json:5-7` 指向 F/ 的 V7 bitstream；本次不重新验证在线板卡身份。
- `F/project.pds:550` 登记 `rtl/parent_tc04_c40cee500c37.v`，实际相机绑定为 `rtl/ov5640_tc03_binding.v`。
- 本次重算 `C/source_hashes.txt` 的 26 项和 `C/candidate_hashes.txt` 的 10 项：全部匹配。按 runner 的纯字节变换重新构造 candidate，和 `cdc_order_candidate.v` 完全相同。
- 读取既有日志确认 baseline/candidate 各 29 例、contract、extra 2 例、long baseline/candidate 各 3 例结束标记均为 errors=0；这些是原有运行记录，不冒充本次重跑。
- `candidate.diff:27-100` 与 transport/展开 RTL 的主要门控一致；`transport.vh` 的 boundary_fault 声明/赋值由 `run.py:21-22` 注入，未在模板内出现不等于实际产物漏接输出。

## P1：实际板级 reset 不能直接套用候选契约

定位：`C/cdc_order_meta.v:14-26` 的 wr/rr 分别清除指针；`C/cdc_order_candidate.v:43-49` 原样传递两个独立 reset；`C/REPORT.md:36` 明确要求联合 reset。

实际连接：

- `F/rtl/ov5640_tc03_binding.v:372,380`：cam_rst=`!cam_rst_n`，video_rst=`video_rst`。
- 同文件 `99-115`：cam_rst_n 是 clk_50m 域上电计数产生的 i2c_start_en。
- 同文件 `119,322`：capture 使用另一个 reset，ov_rst_n=`rst_n & cam_init_done`；不是 CDC 的 cam_rst。`354-359` 的负沿捕获级没有 reset。
- `F/rtl/fpga_v8_cooperative_top_v2_rfg01.v:1025-1034,1046,1258`：camera_ctrl_rst_n 是只启动一次的计数释放；`356-358,1093,1295`：video_rst=axi_rst=`~ddr_init_done`。没有把 DDR 侧复位扩展到相机 CDC 写侧的联合控制。

**本次实际仿真**：写入并排空 64 个像素，保持 cam 域运行，仅拉高 video_rst 后释放，无新源像素，输出累计从 64 变为 128，boundary_fault=0。12/16ns 和板级标称 11.905/7.619ns 两组均复现。读指针回零重新暴露旧条目，不能靠 fault 检出。

分类：不是声称 RTL 在其“联合 reset”承诺内出错；是把候选直接代入当前 V7 时的真实集成缺陷。初始 reset 曾经重叠不能证明运行中单侧 reset 安全，也不能保证所有启动释放次序都安全。

最小修复：增加本地 transport reset/epoch 协调器，任一侧 reset 或 boundary fault 触发双方清空；两域同步释放且均完成初始化后才允许新入队/出队。停止并终结旧 DDR/DMA 事务，重新等待完整帧边界。不要简单给整个传感器/I2C 反复复位代替 transport 协调。

验收：真实 parent/binding 下覆盖 DDR init 丢失、source-only/video-only 请求、两种释放先后、停钟恢复、积压中 reset；不得重放旧像素、跨 epoch 配对或发布旧帧。联合 reset 后首个完整帧逐像素检查。

## P1：boundary_fault 无下游闭环，溢出将永久停止该路

定位：`C/cdc_order_candidate.v:23-30,39,54,66`：满或非法 overlap 锁存 transport_fault，同步后停止消费，只有 cam_rst 清除源故障。

`F/rtl/ov5640_tc03_binding.v:362-385` 的现有 CDC 接口没有 fault；parent 的相机实例 `274-333` 没有 fault 通道；parent 的 DDR `508-527` 只接现有 cam_dma_abort，候选 fault 不在路径内。生成的 `C/candidate/chain.v:53-76` 同样未连接。`C/REPORT.md:35,80` 已披露此限制。

实际影响：短帧剩余数据与关闭 marker 都可能永远不到达；`F/rtl/ov5640_ddr_tc04.v:73-75,119` 的 short 检测依赖后续 raw_sof，不能保证此故障立刻进入 capture_bad。系统其他 DMA timeout 即使退休了事务，也不会清除源 transport_fault，因此不会自动恢复相机流。不能声称候选本身已保证受影响帧的 abort、有限时间退休和恢复。

分类：明确的集成遗漏，不是“看到 fault 即完成容错”。也没有证据证明现有日志曾把短帧错误发布，不能扩大为已复现错误 publish。

最小修复：逐层导出/锁存 fault，接入已有 DMA abort/会话失效流程；处理已发出的 AXI 事务与 FIR 中在途像素，禁止受影响帧成功发布；随后执行联合 flush/rearm。不能只 OR 到 video_rst，也不能只 OR 到一个数据 valid。

验收：在真实 parent/FIR/DDR/DMA 事务模型中分别注入 pixel full、metadata-only full、非法 overlap，覆盖 ADDR/DATA/tag/完成临界点，检查 bounded abort、无错误 tag/publish、故障寄存器可见及下一完整帧恢复。

## P1：Gray RTL 正确结构不等于物理 CDC 完成

定位：`C/cdc_order_meta.v:7-18,21-26` 是二进制/Gray 指针、两级同步和异步组合头读。`async_reg` 是否被 PDS 正确认可尚无实现证据。

现有 `F/inputs/source/constraints/cdc.fdc:57-72` 的示例 max-delay 命令是注释，且目标名称不是 metadata 的 wg/rg；`clock.fdc:62-65` 使用异步 clock groups。不存在候选 wg→ws1、rg→rs1 的已验收约束；旧 V7 STA 无法证明新增逻辑。

最小修复/验收：为两个方向 Gray 总线加工具实际支持且不被异步分组覆盖的 skew/max-delay 控制；目标原则为相邻源更新不会因跨位延迟差在接收端交错，按最快相应源周期取限（CAM1/2 标称 11.905ns，video 7.619ns，可用两者更小值保守约束）。确认同步级不被重定时/合并，提供命中端点和例外优先级报告。另需验收 2048×3 数组的真实映射、组合读 mux 的 video 域时序、存储数据相对已同步指针的稳定性、reset recovery/removal；完整四路资源/布局布线过关。仅 false path 或 RTL 无亚稳仿真均不足。

## 配对/full/同拍读写：未发现契约内必然错配；存在保守拒收

- `C/cdc_order_candidate.v:23-25,43-49`：像素和对应 metadata 共用 put；任一 full 时两个都不写。`40,45`：仅在 pixel 非空且当前 token 有 pixel 时同时读 pixel/pop token；只带 marker 的 token 单独 pop。下降沿+valid token 先降 VSYNC、设置 marker_done，后续读像素再 pop。这避免不同 FIFO 同步延迟直接导致错配。
- `C/cdc_order_meta.v:9-11` 对“下一写指针”预判满，容量 2047，保留一格。满时即使另一域同一物理时刻读出，写域未同步见到空位前拒收是合法的保守异步 FIFO 行为，不能按同步 FIFO 的同拍释放规则认定 bug。
- 本次实际 vendor FIFO 测试：先暂停 video，积压 1000 像素，再恢复并并发输入，经过多次 pointer wrap，11000 个像素全部逐字逐序通过；两组时钟均 fault=0。计数 concurrent_windows 仅表示源边沿采到 rd_en=1，不冒充任意相位覆盖或形式证明。
- `C/cdc_order_candidate.v:23-24` / `transport.vh:9-10` 用 pixel_full 拦截所有 token。因此恰好 1024 个像素把 pixel FIFO 填满后，纯 marker 即使 metadata 非满也会触发 sticky fault。本次实测 accepted=1024、meta_full=0、transport_fault=1，无第 1025 个像素。

最后一项分类：当前报告已写“任何 event 遇 full 失败”，所以是已声明的保守容量契约，不是违反当前文档的静默错配。但产品若要求“像素没溢出时关闭 marker 仍必须送达”，它就是需要修复的行为。最小改法是在资源不足判定中仅对 s_valid 检查 pixel_full，marker-only 只占 metadata；仍保留 source fault/violation 门控。验收 full 前后、纯 marker、下降沿+valid、同拍读写、空/满指针回卷，且两 FIFO 接受的像素数必须始终对应。

## valid & VSYNC：新契约比真实 producer 模块接口更窄

`C/cdc_order_candidate.v:22-30` 拒绝 VSYNC 高时的任何 valid。下降沿+valid 已支持，不能再报“所有边沿同拍 valid 都丢”。

`F/inputs/source/ov5640/ov5640/cmos_capture.v:128-149` 的 valid 仅由 HREF、拼接计数和 frame_val_flag 产生，没有 `!VSYNC` 门控；VSYNC 独立延迟两拍。因此 capture RTL 并未无条件保证新契约，源 valid/VSYNC 重叠时它仍可能输出真实像素；候选会从原先继续传输变为永久故障。

另一方面，DATA_WIDTH=16、实际 binding 的 VSYNC_STABLE_CYCLES=0、每条连续 HREF 正常双字节打包，若传感器引脚满足 HREF 与 VSYNC 高电平互斥，则第二字节的 valid 所对应上一拍 VSYNC 必为低，capture 的两拍 VSYNC 延迟不会凭空造成高/valid 重叠。正常无重叠引脚输入下该契约是合理的，不应把任意构造的 HREF/VSYNC 交叠当作已证明的 sensor 合法波形。

现有板级证据只测 CDC 后高宽 5924/5925 cycles，既不证明引脚 HREF/VSYNC 互斥，也不证明源端每个 valid 都满足 s_vsync=0；末 HREF→VSYNC 间隔尚未闭合。默认寄存器、HTS/VTS 或长高脉宽都不能代替这项证据。

最小验收：对实际 capture+负沿寄存级+候选增加源端 overlap 断言/计数，覆盖真实板级启动与复位，记录持续帧的实际重叠是否为零；同时验证合法下降沿首像素。若接口确需允许高/valid，必须定义其帧归属并有序编码，不能简单屏蔽 valid 或宣称该像素不存在。

## 吞吐和 board 契约检查

- 实际 DATA_WIDTH=16 满足候选固定 16-bit vendor FIFO；模块默认 DATA_WIDTH=24 是继承的泛化陷阱，建议固定为 16 或 elaboration 时拒绝不支持宽度，但当前 V7 实例不是这个 bug。
- 稳态每个无边沿 pixel token 可每 video 拍退休一个像素；marker、guard=3、下降沿带像素和读结果退休等待会占额外周期。不能只比较平均帧频，必须检查最大累计积压（还含满旗同步延迟）。
- 实际板级 video 并非 runner 表中 10ns 的固定假设：`F/rtl/fpga_v8_cooperative_top_v2_rfg01.v:357` axi_clk=core_clk，`F/inputs/ipcore/ddr3/ddr3.v:295` core_clk=ddrphy_sysclk，冻结 `evidence/final_sta_report_timing_clock_summary.xml:98-107` 为 131.25MHz/7.619ns。CAM1/2 约 84MHz，capture 至多每两 PCLK 一像素，正常数据约 42Mpixel/s；CAM3/4 约 24Mpixel/s。标称运行时单路 CDC 服务率有余量，不能把 12/30ns 压力输入当作已证实板级时钟。
- 本次补了 11.905/7.619ns 的近满/并发/回卷仿真，但未覆盖真实四路 parent 的启动/reset/全部流量波形，也不是 PNR 证明。
- DDR busy 丢整帧仍是现有契约；`C/REPORT.md:85` 的 384 输入、256 admitted、2 publish 是正确暴露限制。三周期 guard 只保证 idle admission，不能保证每个 SOF 都被 DDR 接纳。需要逐帧必达时，必须另做 ready/缓存设计。
- Hsync 仍独立同步，只能继续给不依赖逐像素行对齐的消费者使用；debug input/output 快照仍非原子配对，不能据跨帧寄存器读差值直接判丢像素。

## 新增测试、遗漏与最终放行条件

运行：`python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/review_independent/run_review.py`。

实际 ModelSim 输出（两个时钟配置相同结论）：

```text
REVIEW near_full_wrap accepted=11000 output=11000 ... fault=0
REVIEW video_only_reset source=64 before=64 after=128 fault=0
REVIEW marker_at_pixel_full accepted=1024 meta_full=0 source_fault=1
REVIEW_DONE errors=0
```

`errors=0` 的含义是审查断言全部满足，其中包括**成功复现不支持的单侧 reset 破坏行为**，不是候选已通过集成验收。编译 0 errors/0 warnings；每次仿真只有继承环境的 novopt warning。真实 vendor FIFO/primitive，未使用 FIFO stub。日志、TB、runner 和输入哈希全部留在本目录。

原 `tb_contract.sv:9-11,40-44` 强制同一个 rst，因此遗漏了实际板级 reset 拓扑；`58-71` 在 overflow 场景关闭逐字 checker，主要检查故障锁存/可见性，不能证明错误路径 DDR 原子性。新增测试补充局部现象，未替代真实 parent 级容错回归。

放行至少需要：联合复位/重入帧边界实现与实际绑定回归，boundary_fault→事务 abort/恢复闭环及无错误发布验收，Gray/存储路径 CDC 和四路 PNR 证据，板级源 overlap/吞吐契约证据。未完成前只能保留隔离实验候选。

source 偏少必须继续单独调查：有序 CDC 只能保持实际到达的像素，无法把 307199/307198/307193 变为真实 307200。这里正常 source=307200 的回归和短尾 blank 复现不证明板上 source shortage 的成因，也不证明板上末 HREF→VSYNC 就是 1 PCLK。不得补像素、放宽 DDR 长度检查或归因硬件来绕过。
