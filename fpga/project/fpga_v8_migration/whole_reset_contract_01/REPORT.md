# v2 whole reset / fresh ARM generation 审计与恢复提案

结论：**审计已形成；fresh-generation recovery 尚未认证，candidate board load 的复位准入仍为 BLOCKED。** 当前 v2 修正了 ARM staging 和 PCIe H2F，但没有实现全域 recovery barrier。独立 PERST、link-down、CPU/进程重启、DDR init 丢失、局部 capture reset 均不得进入自动 re-ARM / retry。可接受未来把独立复位列为运行时禁止事件，但必须有强制隔离机制和一种经 uniform-reset 测试认证的物理恢复路径，不能仅打印 warning。

本次只写本目录。没有 PDS、SSH、板设备访问、复位、加载、journal provisioning 或 source 修改；WholePnR 单独运行，本审计不读其动态结果来推导验收。Hindsight 服务不可达，结论来自本地原始字节。没有声称 FPGA/RK3568 same-RAW completed FPS 已完成。

## 证据与定位约定

`R = fpga_v8_migration/whole_candidate_v2_route_01/`；以下文件名的 RTL 默认位于 `R/rtl/`。**所有行号均为原文件 1-based 行号**。`source_manifest.json` 保存 927 个所读文件的 path、原始 bytes、SHA256（包含 opaque .vp 的身份，仅可读 .v 用于行为推断）；`source_ascii/<project-relative-path>` 保存关键 RTL 的逐行 ASCII 视图，非 ASCII 字节使用 `\xNN`，不做 GBK/UTF-8 猜测或 replacement 解码。`reset_excerpts.txt` 保存其余原始字节匹配。自动重新采集会更新本目录证据，评审应固定本次 manifest。

登记源：`R/project.pds:678–742`，尤其 `718` 登记 ARM v2，`726–738` 登记 H2F production 四级链，`742` 登记 v2 top。链为 top → `fpga_v8_pcie_fifo_h2f` → `fpga_v8_pango_pcie_top_h2f` → `fpga_v8_pcie_dma_h2f` → `fpga_v8_pcie_dma_controller_h2f`。不是 legacy FIFO 或仿真 shell。manifest 对实际 route 快照取 hash，不能用其他目录同名模块代替。

| 当前 route 原始文件 | bytes | SHA256 |
| --- | ---: | --- |
| fpga_v8_cooperative_top_v2.v | 137922 | a857aecf13e57edb41225e230399273a7a3bebf7e243914e749cb62e15ce1ae1 |
| fpga_v8_capture_control_axil_arm_v2.v | 11428 | b65d5cc7a6e0bc1bdf765dfd6da0bb9488cc0ab27d95fe7e6db730170aa857e9 |
| fpga_v8_pcie_fifo_h2f.v | 31650 | 507ef4c56999aac5356dd51f51a669232fb7c40070c67e3ab108da444b32640d |
| fpga_v8_ddr_adapter.v | 7666 | 5b84936d95c74e10bec28734172b49a175e1a17725bc73b3fade9ae089a5e2b8 |

本地手册证据：`configuration_manual_identity.json` 为安装目录 PDF 的 bytes/hash；`configuration_manual_extract.txt` 为有复位/编程信息的页，PDF page 与印刷页一致。工具源证据也纳入 source manifest。硬 IP 黑盒没有被模拟为“已保证复位”。

## 域、assert / release 与优先级

表中“同步”只描述可见 RTL；没有 reset-domain crossing signoff。共同的 `axi_rst` 不代表外部 release 已同步，也不代表 reset 期间所有时钟仍运行。

| 域 / 状态 | 时钟与实际 assert 源 | release / 同步 | reset 优先级、清除范围与准确证据 |
| --- | --- | --- | --- |
| DDR controller / PHY | free_clk reference；`button_rst_n` 接 vendor `resetn` | `ddr_init_done` 来自 IP；core clock 为 PHY sysclk | top:251,254；controller transaction cancellation / startup 时序须 vendor 认证。不能只凭 init=1 证明旧事务已消失 |
| AXI fabric / crossbar | `axi_clk=core_clk`，`axi_rst=~ddr_init_done` | top:355–358 直接组合，无 fabric reset-release 两级同步器 | top:2414 crossbar reset；button 通过 DDR init 间接触发，不是独立直接 reset net；DDR init 低期间同步 reset 必须实际获得时钟 |
| PCIe physical/reset shell | PCIe `ref_clk`，button/PERST 各经 debounce | shell:203–227，阈值正常 `16'hC000`、speedup `16'h10`；同步器源码 `inputs/ipcore/pcie_test/rtl/hsst_pipe/hsst_rst_cross_sync_v1_0.v:31–81` | 外部低异步拉低 rs flops，再经 inner 低清除输出；release 需同步与计数。不是与 DDR 的 simultaneous release |
| PCIe hard-IP core reset / resetIPO 边界 | hard CTRL 的 pclk / pclk_div2 | shell:68–69 `fifo_pcie_clk=pclk_div2`, `fifo_pcie_rst=~core_rst_n` | `ips2l_pcie_top_v1_8.v:486–496` primitive 接 button_rst、power_up_rst、perst，输出 core_rst_n。resetIPO 字面信号未在本地可读 wrapper 出现；不得臆造其 equation、linkdown 行为、硬 FIFO/posted TLP 清空证明 |
| PCIe shell pclk 控制 / DMA controller | pclk 及 pclk_div2 | shell:230–241 将 core_rst_n 同步到 ref/pclk；shell:357,359,448,532 | 使用 core_rst_n / s_pclk_rstn，受 PCIe reset；不是 DDR reset。shell:555–564 接 sync button 和 sync PERST 到 IP；旧 MSI / host transaction 并无持久 epoch 标签 |
| H2F RX pack / command / completion | fifo_pcie_clk；fifo_pcie_rst | FIFO:166–291 async assertion，直接该域 release | reset 优先，rx count/pack/copy/done 被清；不能清 AXI writer。DMA metadata 跨域随旧事务仍可能存在 |
| H2F RX FIFO 两侧 | wr=fifo_pcie_clk，rd=axi_clk | FIFO:357–369，wr_rst=fifo_pcie_rst，rd_rst=axi_rst | **分裂 reset**。单侧清指针不能证明 FIFO 空、数据新或另一侧不活跃；vendor async FIFO behavior 需两端 coordinated reset 认证 |
| H2F retirement credit | axi_clk 与 fifo_pcie_clk | FIFO:85–105 OR assert；每侧 2-flop release | FIFO:114–141 toggle、sync1/2、seen 均 reset 优先；最后 B 才产生新 credit。OR 仅覆盖 credit，不覆盖 writer、FIFO 两侧和 downstream fabric |
| H2F AXI writer / pending B | axi_clk；仅 axi_rst | FIFO:441–447 **同步** reset，无 PERST 分支 | 清 state、cur_addr、beats_remain、队列、read pending、BRESP error。FIFO:475–487 AW/W/B状态。PERST 时这些旧状态保持；B 被放弃后没有 cancel/epoch reconcile 接口 |
| F2H AXI read / TX FIFO | AXI side axi_rst；PCIe side fifo_pcie_rst | FIFO:504–516 两侧分裂；643–778 AXI read 状态 | AXI outstanding R 或 posted PCIe write 不能被 host timeout / MSI 布尔值取消；CPU/PCIe reset 不保证 AXI读 engine 清空 |
| capture lease manager | axi_clk；axi_rst | lease:108–139 synchronous reset；top:3099–3109 | reset 首先清 generation=0、armed、FREE、claimed/released、sequence/offer；HELD 必须 cooperative 与 host release 都合法后才 FREE（lease:199–204） |
| capture ARM/control endpoint | axi_clk；rst_n=~axi_rst | ARM:143–154 async assertion，release 无独立同步 | reset 优先清 pending、AW/W-held、staged/accepted generation、host-bound、ACK key、计数。staged generation 写不会 ARM；top:3280–3284 接真实 ARM v2 |
| capture datapath / tag FSM | axi_clk；camera_rst=axi_rst OR epoch_start | capture:29,63–99 同步；epoch_start 是 manager idle-only pulse | reset/flush 优先于 pixels；清诊断与4-cycle flush，w_en、pack FIFO、w_ctrl 都用 camera_rst（109,116,131）；epoch_start **不复位 camera DMA / fabric / PCIe** |
| capture camera AXI DMA | axi_clk；axi_rst | top:1590–1595，DMA:299–324 同步 | 外部 final W 后才 BREADY，真实 B 后 done/abort。局部 capture epoch_start 不取消旧 outstanding B；正常 manager 的 engine_idle/all_free 条件必须维持 |
| SFP cam5/6 ingress CDC | wr=sfp_rx_clk，rd=axi_clk | top:1485,1521；sfp_rx_cam_if:44–45,73–91,105–106 | wr_rst_n=sfp_rx_rst_n / rd_rst_n=~axi_rst，两个 FIFO 两端独立。DDR reset 不证明 SFP input 重新定帧；ARM 后必须等待新完整 SOF，不能沿用半帧 |
| 本地 camera CDC | cam_clk 与 video/axi_clk | `ov5640_cdc.v:159,168,216–217,243–244` | wr cam_rst 与 rd video_rst 独立。top:1007–1011 camera_ctrl_rst_n 只是初始化上电计数，不能当全系统 button-reset 完成凭据 |
| cooperative output ownership | core instance 的 core_clk 实际接 axi_clk（top:3167–3168） | control:183–211 async rst_n；其余共同 rst_n | reset 清 FREE/WRITING/READY/HOST_READING、active、source-release、host claim / ACK staging。cooperative core 本身只是 wrapper（163,196,226）；无 persistent reset generation |
| RAW→RGB pipeline / output write | axi_clk；rst_n=~axi_rst | raw_frame_axi:183–215 async assertion | 清 busy、read_pending、serializer、AR、write state 和 frame IDs；WR_IDLE/AW/W/B（89–90）；pipeline_idle（123）不是 whole DMA idle |
| 7-master camera/core write owner | axi_clk；~axi_rst | write_arbiter:126–144 synchronous | owner、ADDRESS/DATA/RESPONSE、计数清；camera/core downstream B owner 不得只在一端 reset 后遗留 |
| DDR adapter write buffer / WB | axi_clk；~axi_rst | adapter:90–96 同步，FIFO rst=!rst_n（41,68–88） | reset 清 write_active/write_hold/vendor_write_active、AW ID/address/len、accepted/consumed W、s_bvalid / v_awvalid、error。WB 表示等待 B 路由状态，此版本没有名为 WB 的独立 register；s_bvalid 只在 vendor last-consumed（124–129）产生 |
| DDR adapter read buffer / SID | axi_clk；~axi_rst | adapter:90–96 同步 | 清 read_active/vendor_read_active、ar_id[6:0]、received/retired R、v_arvalid 和 FIFO。SID 对应保留 route ID：adapter:73–79 `s_rid={ar_id[6:4],fifo_rid}`，直到 last R 被消费（144–148），不是读 initDone 即恢复 |
| Linux owner / allocations / IRQ | RK3568 kernel + process；不受 axi_rst 同步保护 | 无已证实 whole-reset ioctl | retained-source 与 loaded ELF 证据在 driver_ownership_audit；open 清全局 completion，release 释放全局 buffers，不是硬件 cancel。关闭 fd 与无 DMA outstanding 是两个独立判据 |

## 状态阶段与复位后果

没有在当前 audited host/RTL 源找到恢复状态机的字面 `PIPE_*` phases；现有 PIPE_STATUS 是 preprocess 状态寄存器，不是 recovery barrier。下面明确给出业务阶段与实际状态对应，避免把父会话未交付的“latest PIPE”枚举冒充已实现接口。

| 业务阶段（未来 coordinator PIPE phase） | 当前真实状态 / 所有权 | reset 后必须如何处理 |
| --- | --- | --- |
| PIPE_IDLE / BEFORE_ARM | capture all FREE，engine_idle；control endpoint 无 pending | 仍不能推导 RX/TX/controller/DDR idle；先全域凭据 |
| PIPE_CAPTURE_WRITE | lease WRITING；w_ctrl ADDR/DATA/ADDR_TAG/DATA_TAG/WAIT_TAG_DONE（w_ctrl:45–51） | 非共域 reset 可能取消 producer 而 DMA 等 B；禁止重新 ARM；统一复位前保留 buffer quarantine |
| PIPE_RAW_HELD | lease HELD，host / coop 两个 claim-release bits | reset 会丢 hardware lease bookkeeping；旧 host descriptor/token 立即失效，不补 ACK，不释放可能 DMA 使用的映射 |
| PIPE_CONVERT | output WRITING；raw_frame_axi read_pending + serializer + WR_AW/WR_W/WR_B | 旧 AR/R/AW/W/B、源 release 均需 drain 或 uniform reset；不能“core busy=0”替代 drain |
| PIPE_OUTPUT_READY / CLAIMED | output READY / HOST_READING；raw lease 可能仍 HELD | 重置 hardware 为 FREE 不是 host DMA 结束；旧 ownership snapshot 不得交给新 epoch |
| PIPE_RAW_DMA / OUTPUT_DMA | Linux RX slot + F2H read + posted PCIe writes | timeout 留 quarantine；不能释放 coherent pages，不能用 stale MSI 证明新 DMA retired |
| PIPE_ACK / REARM | RAW/coop ACK staging、doorbell 与 readback | delivery uncertain 时 freeze；无需销毁 frame 的完整 CPU copy，但不可据其推断 hardware released |
| PIPE_FAULTED / RECOVERY | helper snapshot、may-exist claim/pending arm | 旧对象不再 I/O；禁止自动 restage/reconstruct/retry；reset receipt + 新 epoch + 新 owner lease 后才生成新对象 |

### 独立 reset 的具体反例

1. 旧 H2F 事务进入 `S_BRESP_WAIT`，此时 PERST 清 PCIe pack/controller、RX wr side 与 OR credit；AXI writer / crossbar / adapter 都未 reset。旧 final B 到来仍可令 `rx_retired_toggle` 翻转。新 command 看到的新 credit 并不必然属于新 command；若最后 B 不来则旧 writer 一直等、或 W 缺数。**OR credit reset 不是 epoch cut。** 这不宣称所有时序必出 stale MSI，而是存在失配路径且没有隔离证明，因此禁止 fresh ARM。
2. `ddr_init_done` 下降仅清 fabric / endpoint / RX rd side；PCIe command / RX wr side、MSI state 可继续保留。DDR init 再上升时旧 FIFO数据 / command 可影响新 endpoint。同步 adapter / writer 若 reset 期间 core_clk 停顿，还需要 reset 跨越恢复时钟的保证。
3. CPU restart 不保证 button 被驱动；PERST 常只影响 PCIe。host journal 正常保留也不能取消 hardware DMA。旧 IRQ 可被新的全局 `g_dma_flag` 消费；MSI 本身不携带 epoch。
4. FPGA program startup 清 fabric 配置状态并不等于 host Root Complex 和内存中的 posted writes / IRQ 被清。需要隔离主机 DMA 内存、确认 IP startup reset pulse 与双方 clock、DDR init recovery，以及 host IRQ synchronization。
5. 独立 capture epoch_start 只清 capture datapath；正常 lease `config_ready` 保护 idle-only acceptance，但它并未检查 cooperative output banks、H2F outstanding B、F2H posted write 或 Linux driver。外部宣称 quiescent 必须由这些事实组成。

## 可支持的物理动作与认证范围

| 输入 / 动作 | v2 的可见覆盖 | 当前认证 / 运行策略 |
| --- | --- | --- |
| button_rst_n 拉低后释放 | DDR resetn + PCIe button debounce；DDR init 决定 fabric reset | **最窄候选 uniform-reset 输入**，但 hard-IP取消、clock stop/restart、SFP FIFO 两侧、新SOF和host memory drain 未证明；目前不得发恢复成功 receipt |
| 同时持有 button_rst_n 与 perst_n，待所有域确认后释放 | button 覆盖 DDR/PCIe，PERST 覆盖 PCIe | 可列为未来认证序列；“同时”不能只靠两个软件写时间，需要示波/monitor 收据、minimum pulse 和各域 sampled-reset 确认 |
| 全板断电冷启动 | 理论上覆盖 FPGA/DDR/PCIe，RK是否同供电未知 | 尚无本地供电/控制 wiring 认证；只可作为人工实验候选，不可当现有 API |
| independent PERST / link-down / CPU restart | PCIe，或未知 link reset；不会直接清 DDR/fabric | 运行时禁止恢复。检测后进入永久 quarantine，必须认证物理恢复路径，不能继续用旧 candidate |
| DDR init transition / controller reset | fabric 清，PCIe 可保持 | 运行时禁止；相同处理 |
| endpoint/capture/core 软件局部 reset 或写新 epoch | 局部 bookkeeping | 无权限作为全域恢复；不能消灭旧 outstanding / MSI |
| cfg_reset_fpga / cfg_program | vendor configuration 操作，不是用户 button / PERST API | 真实命令存在，但 PG2L100H 全域语义与host drain尚未认证；不可静默采用 |

**真实本地 API 可用性（仅查文档，无调用）**：Fabric Configuration 手册 p85 明确 `cfg_reset_fpga -device_index integer-value` 是 FPGA soft reset；p39 “Reset FPGA”操作叙述偏向 Compact，p66 特殊指令 SVF 只支持 Compact，不能由命令名称推定 Logos2 PG2L100H 的 PCIe/DDR等效 button-reset 行为。p84 `cfg_program -device_index 0`；p69 支持 cfg_assign_file。安装 bin 有 cdt_js.exe / cdt_cfg.exe / cdt_cfg_shell.exe。`tools/program_100h_motion.py:173–184` 实际用 SRAM cfg_assign_file+cfg_program 或 JTAG Flash erase/program/verify（非本次候选专用恢复工具）。现有工具没有经审计的 GPIO button/perst coordinated pulse API。`tools/cam3_drv_recover.py:76–79` 的 remove/rescan 被文字称为 reboot PCIe function，实际 sysfs 枚举动作不能证明物理 reset。未用 cfg_help、GUI、JTAG server 或 executable 探测能力。

## durable epoch 与 host helper 的现状

现有 `epoch_allocator/allocate_epoch.py` 已是可复用的纯 Linux allocator：19–21 强制 POSIX/O_NOFOLLOW/O_DIRECTORY；29–50 flock private regular lock；53–70 精确 schema/domain/value 校验；73–97 temporary O_EXCL、file fsync、replace/link、directory fsync 后才返回；100–108 显式 initialize(create_only)；111–121 allocate 只读已有 journal 后递增，耗尽拒绝 wrap。未丢失 journal 时可烧掉未使用 epoch，不可复用。

**provision 限制**：domain 必须绑定稳定物理板卡/FPGA实例及外部 reset 域和 allocator authority，不能仅 PCI BDF/用户名/进程名。独立上界需经可信资产/历史记录证明该域所有曾用 generation 的最大值；新硬件独立证明未用才允许从0 provision。FPGA accepted_generation=0、journal missing、程序启动、重新加载均不是独立上界。现有 initialize API 只接受整数，无法验证该外部证明，应由 provisioning 流程强制记录独立证据 hash 和签发者。路径安全不等于防备份回滚；同域 journal 不可还原旧 backup、复制多 authority、换名再初始化。lost/corrupt/rolled-back/exhausted journal → 禁止 ARM。**本次没有创建任何 board journal。**

`capture_host/capture_host_protocol.hpp:62–65` 的 ArmRequest 两个 booleans 是外部 attestations，131–142 的检查不能证明其真实性。identity、STATUS/configReady、MANAGER_BANK_STATES 和 accepted-generation readback 很有用，但只证明 endpoint/manager 可见事实。不能把 flags=true 当 proof。

helper fail-stop 核对：RAW:127–174 single arm attempt，Uncertain 和异常进入 Faulted；KnownRejected 可返回 Rejected/Busy；DeliveryKnownUnknownResponse 仅已 retired 且有 ordered readback 时可通过 accepted/rejected counters判定。coop:55–58 明确该状态不是 timeout；RAW/coop destructors（120 /136）不 I/O/ACK/reset。copy 后 lease verify；ACK staged words readback后验证同一 lease，再 doorbell/readback。它们没有自动 restaging/recovery，但调用者可重建对象或重新调用 Busy 分支，coordinator 必须禁止用重建绕过 Faulted。不要把 controller MSI 或旧 driver成功返回强行映射为 DeliveryKnownUnknownResponse。F2H KnownOK 必须保证所有 DMA退休和稳定完整 CPU copy，posted write visibility 未证实时返回 Uncertain、保留RX quarantine。

## 最窄未来改动：可观测 guard + 独占 Linux coordinator

优先保留 v2 语义，新增独立可评审分支，不能覆盖现有 PnR。选择一种经过认证的物理 reset 方式，把其余独立事件规定为致命 runtime prohibition。这条路线可接受，前提是下面的硬件与驱动事实能被强制执行。

1. 增加 free_clk 域 recovery supervisor（其 sticky fault 不能被 PCIe/DDR局部 reset 自己清掉），接 actual button、PERST、ddr_init、link-up、PLL/clock-alive。跨域 req/ack 为 level handshake，reset各域 async assert、release local synchronizer；无 clock 时 ack不成立。任何非许可 reset/link-loss 立刻锁闭新的 H2F command、ARM、claim和 capture SOF，保存 reset cause/session nonce；可见 fabric 仍需处理已接受 AXI 的 drain，不能简单切断 W/R/B让 outstanding 被遗弃。
2. 新 monitor 观测而非猜测：H2F writer IDLE、queue=0/read_pending=0、无AW/W/B；RX pack complete/idle + 两侧 empty且pointer-reset完成；controller mrd/mwr not busy、所有 tags/completions退休；F2H read_pending=0、TX两侧 empty；crossbar outstanding counters=0；所有camera DMA idle/B retired；RAW pipeline busy=0/serializer empty；write arbiters IDLE；adapter !write_active/!write_hold/!vendor_write_active/!s_bvalid/!v_awvalid + writeFIFOempty，read类似含R FIFOempty和SID生命周期结束。不能单取 adapter write_busy（64）忽略其他 buffer/hold事实。
3. `recovery_safe` 快照必须包含硬件 session nonce、reset cause、所有域 ack 和 monitor 值；snapshot 全部 idle稳定且锁闭新 submissions才能有效。capture/control端 `configReady` 只是其中一项。nonce 与 boot/device/build identity绑定；旧 snapshot、旧 user process、旧 epoch、旧 IRQ均不能续授权。
4. independent reset 若只清 PCIe credit、writer不同reset保持 → 明确 FAIL，不能通过 OR writer reset 粗修：否则下游已接受 AW/W 的 B会遗留。统一 reset 需包括 DDR controller/fabric/adapter和全部 producer/consumer，或显式 drain+abort协议且真实last B/R有凭据。
5. Linux driver 加 admission-close + DMA drain/quarantine ownership；在 active DMA 退完前不得 `release` free coherent buffers。取消camera/NPU自动排队并明确处理 g_dma_flag、pending counters；disable new submissions、屏蔽 IRQ并 synchronize_irq，驱动恢复设备后清理 old completion与 pending status。IRQ drain本身不是PCIe posted write drain，需vendor/hard-IP/RC ordering保证或可验证 completion fence。仅 stop viewer/close fd 不足。
6. coordinator持有全局 kernel/transport owner lease和软件跨进程锁；只由它创建 ArmRequest。授权结构采用不可复制一次性 ArmPermit(epoch, physical-domain, journal-commit digest, hardware-session, owner-lease, bank/RX reservation)，getter内部读取有效状态。任何 reset/fault/timeout令 permit失效。不接受外部JSON布尔值直接 ARM；离线 JSON最多是缺口清单。

### 恢复操作顺序（提案，当前不可执行成功）

关闭 admission → 停全部viewer/benchmark/camera/NPU producer → 确认真正driver owner退出与所有fd/mmap注销，**但先 drain 硬件，避免现有release提前free** → 若有不确定DMA则保留quarantine pages并进入认证物理恢复流程 → 用已认证physical operation重建全域session → clear/synchronize旧IRQ、验证新枚举identity与构建 → 获取monitor idle收据 → 建立唯一driver owner和实际RX allocation容量 → 验证四bank排他及control/RAW/output RX slots无重叠 → allocate并持久化新epoch → 读取endpoint ID/version及configReady、bankstates/pending/accepted counters → stage generation/readback → ARM一次 → readback accepted generation+accepted_configs增1+armed+无pending/fault，rejected不增 → 开放新SOF → 之后claim/pair/copy/ACK每步继续核对session/generation/token。

新增driver owner本身会改变全局completion状态，必须在allocator/ARM前，且不可在driver owner变更后复用旧permit。ARM readback不是首个I/O：**endpoint/configReady/readback必须先于ARM doorbell**，stage后还要readback。

## prompt → artifact 成功判据

| 请求判据 | 本次证据产物 / 当前结论 | board load前还缺什么 |
| --- | --- | --- |
| exact v2 ARM+H2F production登记 | source_manifest、source_ascii、上面的链与行号 | 后续修改必须新分支、新hash与登记审查 |
| 每域 reset/assert/release/clock/priority | 本报告域表、reset_excerpts | resetIPO/hard-IP取消和clock恢复认证 |
| quiesced driver owner closed | 本地既有driver audit来源已核；未访问当前板 | 当前boot+pid/starttime+fd/mmap+admission/drain receipt；不能复用历史PID |
| no DMA hardware outstanding | v2缺全域可读monitor，BLOCKED | supervisor、AXI/DDRadapter状态、PCIe posted-write fence、IRQ drain |
| DDR四bank排他 / RX capacity verified | raw 0x01800000/0x01a00000 +614400+16，output 0x08000000/0x08200000 +1228800；top:3090–3097,3162–3164 | actual dynamic CAM1–4及所有writers地址不重叠；实际allocation/mmap容量与slot范围验证，非传入常量 |
| newepoch persisted | allocator代码审计，未provision/allocate板journal | 稳定physical-domain身份、独立上界provision记录、durable allocation receipt、防回滚authority |
| endpoint readback/configReady first | RAW helper:134–148；ARM:150–173 | 真实transport ordered-retirement保证，session/monitor准入 |
| independentreset fail-stop/no stale ACK/MSI | 风险反例、helper停止与future guard设计 | public-port动态回归 + driver/hard-IP验证；当前不能宣称stale MSI防护已实现 |
| same RAW completed FPS | 未运行，未验收 | 同generation/sequence/token paired完整RAW与RGB输出、CPU完整copy、相同输入推理与completed计数，恢复期不计completed FPS |

## 仿真边界与下一个可评审测试

本次未运行 whole PCIe/capture cycle simulation；保留审计优先，未以假 hard-reset mock 或离线 coordinator 作硬件凭据。既有 pc ie retirement run_tests 的shell模型和真实FIFO/controller能验证最后Bcredit，但不能认证PERST到hardIP取消、DDRinit与physicalstartup。当前也没有实现禁止事件检测的guard，无法诚实要求“独立reset必然hardware failstop”的PASS。

后续在新目录用 exact route RTL、real Pango FIFO+controller+ARM endpoint+capture lease/core，shell仅model public reset输出，公口注入：正常idle uniform；AW已接受/W未完成；lastW后延迟B；B已retired但credit未过CDC；capture WRITING/tag WAIT_TAG_DONE；lease HELD（host/coop分别持有）；output HOST_READING；R/TX/posted F2H悬挂；PERST-only、AXI-only、capture-only、linkdown、CPU restart(no fabric input)、startup停钟/错序release。分别记录AW/W/B、R、MSI、bankstates、ARM accept/reject和generation。无层次force内部state、无把reset input同时偷偷联动；unsupported cases的当前期望是展示reset差异/拒绝认证，而future guard回归才断言隔离后无新ARM/ACK/MSI。旧B延迟注入必须证明不能给新commandcredit；任一clock停转不能获得uniform-safe receipt。再做hard-IP与物理button/PERST认证测试，才能允许 runtime prohibition 路线。

本目录有 `verify_audit.py` 静态字节/登记检查；它证明本报告的核心断言和 source hash一致，不是cycle仿真、硬件复位或上板验收。Linux offline coordinator prototype本次有意未实现：无可信实际monitor/driverprovider时，把booleans包装成API不增加证据；已给出ArmPermit接口和接入顺序，下一改动应先提供真实观测provider。

已执行 `python .../whole_reset_contract_01/verify_audit.py`：927 个已采集原文件 bytes/hash复核一致，16项静态登记/复位/allocator断言通过，结果在 `validation.json`。该结果明确 `board_recovery_certified=false`、`journal_provisioned=false`、`cycle_simulation_run=false`。仅审计交付可判完成，安全恢复与候选上板准入尚未完成。
