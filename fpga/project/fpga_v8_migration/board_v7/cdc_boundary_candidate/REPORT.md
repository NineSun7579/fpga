# 有序 CDC 边界修正候选（隔离实验）

## 结论与范围

本目录保留真实 vendor 1024×16 像素 FIFO，新增自有 2048×3 metadata FIFO；不修改冻结目录、production、ipcore、RAW 数据或 DDR 长度判定。只做本机 ModelSim 仿真，没有 remote、program 或 PDS 工程改动。当前是供审查的候选，不是已批准上板修复。

最终仿真结果见下方实测章节。原有 source-domain 307199/198/193 现象仍未解释；本机制的复现输入 source=307200、drop=0，不能据此声明板上根因。

## 为什么采用有序 metadata

### 新纳入的已核实板上时序证据

本地既有 `board_v7/run_20261006_141824_27582c99/runtime/input_diagnostics.json` 中 CAM1/2 的 `vsync_width=388241189=0x17241725`。冻结 `parent_tc04_c40cee500c37.v:554–574` 在 **CDC 后、FIR 前** 按 video_clk 周期统计高电平，703 行打包 `{min,last}`，故解码为 **min=5924、last=5925**；少数记录 last=5924。它不是 388241189 个周期，也不是源 PCLK 宽度。该证据表明记录中的板上 marker 并非窄脉冲；本目录 1-PCLK pulse 测试用于接口压力覆盖，不作为板上波形解释。

必须区分 **末 HREF→VSYNC 上升沿的尾 blank** 与 **VSYNC 上升沿→下降沿的高电平宽度**。已测 5924/5925 周期仅约束后者，前者仍未知。源配置 HTS=1896、VTS=984 与 640×480 输出几何不能直接相减推出尾 blank，也不能证明本目录 tail=1 PCLK 是板上已证实合法的波形。

本地 `project/sim/edge50k/evidence/OV5640_datasheet.txt` 的 4709/470A/470B 默认字段分别为 02/00/01，即 2 lines + 1 PCLK 的宽度字段；471D 默认 01 描述帧末触发 VSYNC 正沿。按已核实的初始化检查，这些寄存器及 4740 均未被显式写入。默认字段不是本次 sensor 活跃配置回读，也没有建立末 HREF→VSYNC 的具体间隔。上述证据不支持硬件归因，source 偏少仍未解释。

`run.py --long` 新增约 5925 video 周期的长电平回归，并同时测量首/尾 marker 高宽：12/16ns 使用 7900 PCLK，12/30ns 使用 14813 PCLK。长 pulse 与 tail 分别设置，覆盖 tail=2000 控制及 tail=1 压力案例。初始及关闭 marker 都使用该长脉宽，仍要求真实 DDR 完整 admission/publish，不以单拍 SOF 替换电平。

候选维持电平直到有序下降 token 退休。若关闭 marker 前有像素积压，上升沿需等待尾像素，下降沿通常无需相同等待，因此输出高宽可能缩短；它不承诺精确保持 5925 周期。回归会明确记录该变化，不能把“保持长电平契约”写成“保持物理脉宽不变”。若未来消费者需要逐周期脉宽保真，则需另加时间戳/宽度重放契约及容量分析，超出当前最小候选。

固定推迟 VSYNC 无法覆盖随时钟比、行宽和 FIFO 积压变化的像素延迟。候选对每个有效像素写入一个 pixel token，对每次 VSYNC 电平变化写入一个 level token，二者共用一个源端顺序。像素数据仍通过原 vendor FIFO。读端只有消费 pixel token 才读取一个真实像素；level token 必须等待之前同步 FIFO 读结果退休才可重放，保证最后一个有效像素严格先于下一个 VSYNC。

VSYNC 升沿之后暂停取 token 三个 video 周期，为既有 DDR admission 流水线提供启动间隔。这是下游接口需要的局部间隔，不是通过固定延时猜测尾像素是否已经排空。下一帧数据和降沿也排队，不靠源端 blank 保证该间隔。

具体依据是冻结 `ov5640_ddr_w_en.v` 中 `s_vsync_ff`、`s_vsync_rise`、`curr_state` 的寄存器路径，以及 DDR 的 `m_vsync` 打开 capture 路径。rise token 后还有有序 fall token 和同步像素 FIFO 读周期；最紧输入的真实 FIR/DDR 集成仿真用于检查间隔充足，不能任意删掉 guard。

保留 VSYNC 升降沿和 high/low 顺序；输出 high 宽度可被排队和最小启动间隔拉长，空队列时也受跨域同步量化，因此**不保证输入脉宽的时间等长复制**。不能把该输出当作传感器物理时序测量信号。只有在 cam 域被采样到的窄脉冲才保证入队。输出 marker 不与 valid 同拍，连续 marker 至少有一个 video 低电平周期。

## 严格接口契约及尚需集成的部分

1. 适用 DATA_WIDTH=16（真实 FIFO 的固定宽度），源端有效像素必须处于 VSYNC=0。允许下降沿同拍 valid：token 的 transition/pixel/level 三个位同时记录它，读端先降低 VSYNC，再读该首像素。高电平（含上升沿）同时 valid 则锁存故障，不猜测像素归属。首版禁止所有 transition/valid 重叠，在真实 capture 的窄 VSYNC 测试中失败，故修正了该过严约束；未放宽像素检查或长度。
2. 源端没有 ready，任何有限 FIFO 都不能接纳无限超速输入。平均吞吐和最大 burst 必须满足容量。metadata 满、pixel FIFO 满、非法 overlap 都进入 sticky fault，停止新入队，video 域同步该故障后停止继续读出，直到联合 reset。故障同步之前已输出的前缀不能撤回。
3. metadata 满可能没有任何像素 drop，因此现有 dbg_cdc_drop=0 **不代表 metadata 健康**。新增 `boundary_fault` 输出为 video 域同步后的 sticky 故障，单测检查其可见性；上层必须连接它到 abort/reset。集成对照 TB 的旧 chain 没有把它接入 DDR，因此仅靠旧接口不能承诺 overflow 时完整帧原子性。本目录不伪造 DDR completion，不把故障短帧标为成功。
4. cam_rst/video_rst 必须联合断言，并保证双方时钟运行完成初始化；重新释放应遵守各域 reset 时序。独立单侧 reset 不支持，因为会破坏两条 FIFO 和 token/像素的对应关系。必须丢弃 reset 前尚未结束的下游事务并重新等待帧边界。仿真覆盖的是联合 reset，不模拟亚稳态。
5. DDR 没有帧 ready/marker replay 接口，engine_busy 时仍可整帧跳过。三周期启动间隔只解决 idle DDR 的 admission 流水线，不保证前一帧及 tag 在下一 SOF 前退休。若需求是连续紧邻帧无条件全部发布，需要增加下游握手与足够整帧缓冲，超出本候选范围。
6. Hsync 保持原有独立同步方式；候选只对 VSYNC/pixel 顺序建立契约。不能向依赖行边界精确对齐的新消费者承诺 Hsync 和数据同步。
7. source counter 与 snapshot/toggle CDC 保持原逻辑；超密 marker 时原 debug mailbox 仍不保证逐帧快照交付。candidate 的 dbg_cdc_output 改为跟随 video 域实际 out_snapshot，不再在早到的 source toggle 时抓取旧 output snapshot；两个域的 debug 快照不是原子配对接口。

## RTL 可综合性与物理限制

`cdc_order_meta.v` 使用静态寄存器数组、单写时钟、组合头读取、二进制/Gray 指针及双寄存器同步，不使用 delay、initial 初始化、动态数组或仿真专用 FIFO。容量保守保留一个位置（2047 tokens）。`transport.vh` 是生成候选 CDC 的可审查差异块；`cdc_order_candidate.v` 为实际编译展开产物，source counter 由冻结版本提取。

这是可综合 RTL 结构，不是已验证的目标器件综合/布局布线结果。metadata 组合读可能映射为寄存器/分布式 RAM，资源和频率未测；Gray 总线仍需目标工具认可的 synchronizer 属性、跨域总线 skew/max-delay 约束及 CDC/时序审查，不能只加 false path。没有在共享 PDS 工程上启动实现。没有用仿真声称物理 CDC 安全证明。

## 复现与证据

从工作区根运行：

```powershell
python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/run.py
python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/run_contract.py
python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/run.py --extra
python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/run.py --long
python project/fpga_v8_migration/board_v7/cdc_boundary_candidate/summarize.py
```

runner 复用 `capture_boundary_integration/tb_integration.sv` 的 capture、真实 FIR/DDR、DMA completion model、逐像素队列与检查器，只替换测试选择、扩大连续 VGA 的 checker queue，并为 candidate 替换 CDC 模块名。baseline/candidate 使用同一 stimulus。真实 vendor CDC/DDR FIFOs 和 PDS RAM primitives 均直接编译。DMA endpoint 仍只是事务退休 TB 模型，不是 DDR/PCIe 系统。

`baseline/`、`candidate/`、`contract/` 保存独立 compile/simulation 日志。`source_hashes.txt` 比较执行前后冻结/vendor/原集成 TB 的 SHA256。候选新增模块名已在目录外所有 project `.v` 中按字节扫描，无重名。

## 实测结果

实际执行日期为 2026-10-06。baseline 15:27:09–15:29:11，最终 candidate 15:32:13–15:34:27；两者均 `CANDIDATE_DONE cases=29 errors=0`（这里 DONE 名是共用 TB 标记，baseline 包含明确要求复现的失败行为）。逐例数据在 `results.csv`，可审查差异在 `candidate.diff`，候选代码摘要在 `candidate_hashes.txt`。

| 同一输入条件 | baseline DDR admitted / publish / short | candidate DDR admitted / publish / short |
|---|---|---|
| VGA，cam/video=12/16ns，tail=1 PCLK | 307199 / 0 / 1 | **307200 / 1 / 0** |
| VGA，cam/video=12/30ns，tail=1 PCLK | 307070 / 0 / 1 | **307200 / 1 / 0** |
| VGA，11.905/10ns，tail=2000 | 307200 / 1 / 0 | 307200 / 1 / 0 |
| VGA，12/30ns，tail=2000 | 307200 / 1 / 0 | 307200 / 1 / 0 |
| VGA，12/16ns，连续三帧宽裕 blank | 921600 / 3 / 0 | 921600 / 3 / 0 |
| 32×4，pulse=1 PCLK，head=0，六种 video 周期×四相位 | 18/24 场景发布，6 场景丢首 marker | **24/24 场景各完整发布** |

所有完整 VGA 单帧输入/source snapshot/总 CDC 输出均为 307200，source drop=0；candidate 的 CDC/DDR 帧窗口也均为 307200。三帧连续实验无 reset，逐个窗口都是 307200，累计 921600 个像素逐字逐序通过 checker。窄 VSYNC 的 candidate 首像素距 SOF 均为 5 个 video 周期，真实 DDR admission 无首像素损失。

在 12/16ns、tail=1 的 candidate trace 中，最后 CDC valid 比 VSYNC 升沿早 32ns；FIR 保持相同顺序。原 baseline 两者同拍，DDR 拒绝最后一个像素。12/30ns 积压案例中 candidate marker 在全部尾像素之后 60ns 到达，而 baseline 提前 3870ns。没有补像素、改 RAW 数据或放宽长度判定。

编译均 0 errors/0 warnings；baseline 仿真 15 warnings，candidate/extra 各 17 warnings，来自继承的 `-novopt`、TB 未接诊断输出、原 vendor FIFO 未接 water-level 输出，以及旧 chain 未接新增 `boundary_fault` 输出。没有未连接的必要输入；该 fault 输出未接入 DDR 的限制已在契约中明确。

已完成的额外契约测试：

- `contract/simulation.log`：800 个有序像素、101 个窄 marker，包含下降沿同拍首像素；metadata-only overflow、pixel overflow、非法 high/valid overlap、积压期间联合 reset 后恢复，`CONTRACT_DONE errors=0`。检查输出 valid 与 VSYNC 不重叠、marker 对应的已输出像素数、逐像素数据和首像素 admission 间隔。编译 0 error/0 warning，仿真仅继承 `-novopt` 的 1 个 warning。
- `extra/simulation.log`：零 tail blank 的 128 像素帧也完整发布；保留原集成的 busy gate 实验，三帧输入/输出各 384，DDR admitted=256、published=2、short=0，`CANDIDATE_DONE cases=2 errors=0`。因此有序 CDC 没有把 DDR busy 丢帧掩盖为已解决。
- 与原 `capture_boundary_integration/source_hashes.txt` 的 26 个冻结/vendor 输入 SHA256 再比对，全部一致；本目录 runner 也检查其执行前后输入一致。

### 长 VSYNC 增量回归实测

`long_baseline/simulation.log` 与 `long_candidate/simulation.log` 均实际结束，分别为 `CANDIDATE_DONE cases=3 errors=0`。下表高宽单位是 CDC 后、FIR 前的 video_clk 周期，位置与已核实的板上统计一致。

| cam/video ns，tail PCLK | baseline 首/尾高宽 | candidate 首/尾高宽 | baseline admitted/publish/short | candidate admitted/publish/short |
|---|---|---|---|---|
| 12/16，2000 | 5925 / 5925 | 5925 / 5925 | 307200 / 1 / 0 | 307200 / 1 / 0 |
| 12/16，1 | 5925 / 5925 | 5925 / 5924 | 307199 / 0 / 1 | **307200 / 1 / 0** |
| 12/30，1 | 5925 / 5925 | 5926 / 5796 | 307070 / 0 / 1 | **307200 / 1 / 0** |

所有场景 source/snapshot/总 CDC 输出都是 307200、drop=0，逐像素队列比对通过。长 VSYNC 本身不会修复提前到达的上升沿；candidate 通过有序传输修复，且输出仍为数千周期的高电平，未退化为单拍 marker。12/30ns 的 5796 周期明确反映等待积压像素对电平宽度的影响，不与板上 5925 周期混同。

这些仍是**长脉宽条件下的短尾 blank 压力复现**：证明机制不依赖窄 VSYNC，但不证明板上末 HREF→VSYNC 只有 1 PCLK，不解释 source 307199/198/193，不归因硬件。追加只改隔离 runner、TB 与报告，候选传输 RTL 无需改动；没有任何板端操作。
