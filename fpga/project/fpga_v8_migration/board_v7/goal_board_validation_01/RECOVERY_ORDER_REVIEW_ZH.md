# Session rebuild 恢复顺序审查

## 结论与范围

**推荐把完整、已签核 V7 recovery SRAM 重载移到主机 reboot 之前；最终 build03 则研究“父桥 SBR 保持 → 完整编程 → release → 枚举/绑定”的启动顺序。** 这消除了旧报告中“reboot 后 probe 自动恢复 BME，而旧 fabric descriptor 尚在”的具体原因，不需要跨 reboot 保持旧 endpoint 的 BME=0。最终保持 SBR 编程的硬核启动可行性尚未证实，不能把推荐次序签成 actual PASS。

本次仅新增此报告；未连接 RK3568、未打开设备、未进行 BAR/DMA/config/sysfs/GPIO 操作、未 reboot、未运行 PDS 或 programmer。读取本地冻结输入、已有 receipts、安装版官方 IP PDF/primitive wrapper，并读取公开 Linux v6.1 寄存器定义。Hindsight 服务不可达。所有下文执行动作均为未来步骤；既有烧录记录不充当本次 recovery 回执。不改 consumer、RTL、其他 agent 文件、合同或验收要求。

审查目标是可推进的 session 取消/重建，不追认旧 DMA 成功或 drained，不要求新增 AXI idle/readback 硬证书。三项最终交付仍是新合格 bit、实际 SRAM 编程、RK3568 实际截图及运行结论，均须真实 consumer 独立验收。

## 1. 本次核验的依据

令 `V=../whole_candidate_v7_route_01`（相对 board_v7），`N=../source_diagnostics_timing_build_03`（相对此 goal 目录）。

| 本地核验项 | 结果及边界 |
|---|---|
| V7 recovery bit | 实际读取 `V/bitstream_01/generate_bitstream/fpga_v8_cooperative_top_v2_rfg01.sbit`：3,791,112 bytes；SHA256=`dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`。这是已有 qualified V7，不以未签核 new candidate 替代恢复镜像。 |
| 已有 vendor SRAM 记录 | `../run_20261006_141824_27582c99/receipt.json` 与 `log/cfg.log:18–35`：单 PG2L100H、cfg_program 成功、最终 DONE=1；receipt 的 `board_operation_verified=false`。证明此 bit 曾实际 SRAM 编程，不能证明 held-SBR 启动或本次恢复。programmer SHA256 保存为 `c9719f35b5ef827d04b77b6088ac27ef88e2cea72898461a4cdfb98657e0660f`，本次未运行/重新签核工具。 |
| 当前 reset 接口 | `reset_interface_readonly01.stdout.json` 留存 `reset_method=bus`、FLReset 不支持、0755:0755 endpoint；这是实际方法登记，尚不是执行 reset 回执。 |
| GPIO144 排除 | `CURRENT_RESET_INTERFACE_CORRECTION_ZH.md` 及 raw DT：bank4 pin16 属于 `/dsi@fe070000/panel@0/reset-gpios`；不是 PCIe PERST。vcc3v3_pcie regulator-fixed 没有 gpio/gpios 开关。PCIe live node 没有 reset-gpios；不能据此推论物理 PERST 不存在。 |
| 现有 consumer | `new_program_candidate.py:490–508`：保留 owner/driver/身份及 300 秒新鲜度要求；rebuilt 分支要求 action、boot_before/after、实际枚举/绑定，且 before!=after、after==current。`new_validate_board.py:278–282` 保留运行证据的 boot 绑定。 |
| build03 | 本次本地搜索 N 下没有 `.sbit`；build03 RTL 已有，但最终 qualified bit 与 actual delivery 验收尚未产出。不得提前写 bit SHA、accepted 或 program PASS。 |

GPIO144 stdout receipt：UTC `2026-10-06T23:36:36.536064+00:00`、exit_code=0、SHA256=`18bbd86876b2ed509b1c2f57c057ce3dbe21fac6b5a62a7022ea0f001ee7f6db`。provider stdout receipt：UTC `2026-10-06T23:36:19.005294+00:00`、exit_code=0、SHA256=`20222d8d848b6584d1baaae90e9122026d7c4c86d281ffa91fd5252a8c87b81c`。二者均明确 device_opened=false、reset_executed=false。

## 2. 为什么重载提前可以去掉旧阻塞原因

旧顺序是 clear BME → bus reset → reboot → 完整 SRAM。新内核/驱动在最后一项之前可能设 BME，旧 descriptor/FIFO/AXI 控制状态有机会继续使用已复用的 host 地址。一次 BME 读回不能覆盖这个窗口。

修改为 clear BME actual readback → bus reset（入口和出口 BME=0）→ **完整旧 qualified V7 SRAM 重载成功** → reboot。旧用户逻辑 descriptor、FIFO、AXI 控制状态与 persistent guard 的失效点已经在新 allocator 出现前。此后即使 probe 重新设 BME，也不能让已被完整重配覆盖的旧用户引擎恢复旧 session。期间禁止 device open、用户 DMA、新提交及驱动自动发起事务；no-owner 与 stop-admission 必须真实保持，不能仅靠空 fuser 或一次 BME 读回。

这是重建旧事务权属的因果顺序，不是声称 SRAM 会擦除外部 DDR 内容。旧 DDR payload 可以残留；旧 bank/lease/descriptor 权属必须随完整配置初始化作废，不再作为命令重用。单独 SBR 不承担全 AXI fabric 清理，完整配置才承担用户 fabric 重建。BME 禁新请求也不追溯取消已发送 TLP：initial bus reset 与后续主机重新启动属于取消/重建边界；现场保留实际 reset/boot/RC 重新初始化记录，异常时停在对应步骤，不额外发明“全部历史事务已 drained”的验收项。

旧 V7 recovery 在 link 恢复后可能自行 qualified；reboot 随后的 link/reset 变化可能使其 guard fault。这一中间镜像只是取消旧状态的桥接恢复镜像，不承担最终运行 PASS。reboot 后最终 build03 完整配置重新初始化 guard，所以允许中间镜像 fault，不能据此重复尝试 DMA 或将其认证为运行正常。

## 3. startup qualification 不是常量，也不要求 host open

核查实际 frozen RTL，而非 sim_views 替代文本：

- `V/rtl/fpga_v8_pcie_fifo_h2f_tc02.v:83–87`：`startup_idle_axi=(state==S_IDLE) && !rx_read_pending && rx_w_queue_count==0 && r_state==R_IDLE && !read_started`；PCIe qualification 检查 mrd/mwr busy、copy、FIFO 写使能和 data_wry_state。**不是 constant 1。**
- `V/rtl/fpga_v8_cooperative_top_v2_rfg01.v:442–454`：guard 的 AXI qualification 还包含 capture engine idle、未 armed、capture/cooperative bank state=0、cooperative/bridge/arbiter 不 busy。该实例的 fault/runtime 输出没有导出为 host 状态寄存器。
- `V/rtl/fpga_v8_reset_fault_guard_02.v:18–26,46–65`：health 包含 button/perst、PCIe/AXI reset、DDR init 和两个 link-up；两个域 heartbeat、同步后的 startup idle 与 32 个 free_clk qualification 周期可自行使 `runtime_active=1`。无需 host open/DMA/BME=1。
- runtime_active 后 health 下降或 heartbeat 超时锁 fault；fault 没有局部 reset 清除路径。startup 阶段 health 持续低会使 qualification 清零、admission 关闭，**前提是硬核实际 link/reset 状态确实让 health 保持低**。

因此 `finalprogram → busreset` 存在真实故障路径；“还没打开设备”不能排除此路径。held-SBR 方案的价值是把最终 link 恢复放在 startup qualification 之前，而不是用 SBR 代替全 fabric reset。

本次字节 SHA256 比较结果：

| RTL | V7 | build03 |
|---|---|---|
| cooperative_top | `ca02da78385c7b9f156373748c5e46cc47f9a104b006778a99a35200d2991841` | 同 hash |
| pango_pcie_top | `2a36809233007d09b0f4583bfcaaed4876f56b54fa4802cec36c07edc1225351` | 同 hash |
| TC02 FIFO | `44c8cb76e5353415d2ee8c204331663f66fc3671158a3389e0d89b5e2a0f246c` | `08b55c01443d86c9e38cf1822af785acb89d4643be02850da0b5ba0f4d605c66` |
| guard_02 | `e5a61f4085c4691387c10a8000aa74eb1c50c0ad3ee1a2d12f3a48d74038e9dd` | `752627126b80e3683518cd7f37b2213e56a6e66e52507d1ffb5ddb55ed29fb38` |

FIFO 与 guard_02 的完整文本 diff 仅见同步寄存器属性由 ASYNC_REG 改为 syn_preserve/syn_allow_retiming；上述 qualification/health/状态机表达式相同。**逻辑表达式一致不等于全文件同 hash，更不等于最终物理实现已经签核。** build03 必须绑定自己的实际编译 closure、route 与 bit；不拿 V7 hash 或本次 review 替代。

## 4. 官方接口可以说明什么，尚不能说明什么

安装版 `C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ips2l_pcie_gen2/ips2l_pcie_gen2_eval/ips2l_pcie_gen2/UG042004_Logos2_PCIe_IP.pdf`，83 页、SHA256=`9deba94b50770cd6cf380421f0cb04bffb3f229d37e5cf6d338bdacce74c7d33`：

- p54 表2-23：Command bit2 BME=0 禁止发送 MEM/IO 类请求；reset 值为0。没有把此位解释为全域 idle、历史 TLP drain 或全部 Message/Completion 禁止。
- p35 表2-20：power_up_rst_n 与 perst_n 是低有效、来自插槽 PERST#；core_rst_n 是供用户逻辑使用的硬核输出复位。p36 列 HOT_RESET_ENTRY/HOT_RESET，证明硬核有 hot-reset 状态，未给出“PERST 常高、配置后首次启动处于 held hot-reset”的完整初始化保证。
- p16 框图区分 GTP_PCIEGEN2 协议硬核与包含 HSST 复位序列的 soft PHY。不能只凭 LTSSM 枚举推出 HSST/power-up 复位要求均满足。

冻结 top 中 perst_n 是输入（cooperative_top:43），不是 RTL 常量；pango wrapper:226–230 将其 refclk debounce/sync 后，:559–560 同时接到 power_up_rst_n 与 perst_n。`inputs/source/constraints/pcie.fdc:37–41` 指定 M16/LVCMOS33；`V/project.pds:1431` 登记这个约束，IP example 的 L4 不能当作当前板 pin。**物理 PERST 是否被拉高、上电/重配是否有真实低脉冲、板级驱动来源仍未知。** DT 排除 GPIO144 不填补这个物理事实。

冻结 `inputs/ipcore/pcie_test/rtl/ips2l_pcie_hard_ctrl_v1_8.v:625,650–654` 接到 GTP_PCIEGEN2，CORE_RST_N 与 TRAINING_RST_N 是不同输出。安装版 `arch/vendor/pango/verilog/simulation/GTP_PCIEGEN2.v`（SHA256=`1bde8f90120dfc46bab106d4ba8585b199078b9de6f9287a4df00ce4ff71e420`）:56–62 声明 BUTTON_RST/POWER_UP_RST/PERST/CORE_RST_N/TRAINING_RST_N，:288 起再例化 PCIE，:319–322 只是转接这些端口。该公开 wrapper 未展示首次启动内部复位状态机，**不能据此证明 SBR 可替代 PERST，或 hot reset 必定拉低 CORE_RST_N**。

Linux 官方 [v6.1 pci_regs.h](https://github.com/torvalds/linux/blob/v6.1/include/uapi/linux/pci_regs.h) 定义 `PCI_COMMAND=0x04`、`PCI_COMMAND_MASTER=0x0004`；type-1 `PCI_BRIDGE_CONTROL=0x3e`、`PCI_BRIDGE_CTL_BUS_RESET=0x0040`，即 bit6。未来保持动作应通过识别出的真实父桥 config **word 掩码写**，仅改 bit6：assert 等效 `new=(old & ~0x0040)|0x0040`，release 等效 `new=current & ~0x0040`；其余位不变。若用支持 data:mask 的现有配置工具，语义为 `0040:0040` / `0000:0040`，不对 endpoint 的 0x3e 写桥位，不盲写整个 bridge-control 常量。此处仅说明官方寄存器语义，未执行命令。

`REBUILD_SEQUENCE_REVIEW_ZH.md:25–41` 已审查 sysfs function reset 的 bus 方法及 save/disable/restore：必须在入口 BME=0，否则配置恢复可能带回 BME=1。该 sysfs reset 是一次 assert/release，**不能用它来保持 SBR 跨编程**。父桥手动保持也不能假定等同当前下游 kernel 实际 sysfs 路径；要记录真实父桥和作用域，协调驱动/AER/rescan，防止并发释放 SBR 或恢复配置。公开 Linux v6.1 是接口依据，不冒充当前 6.1.99 下游实现身份。

## 5. 可推进的实际顺序与回执

下面是供主会话执行和独立审核的步骤，不是执行记录。无需等最终 build03 产生才完成本地文档/接口核对；recovery 实际动作遵循已有 SRAM 工具授权和签核边界。

| 步骤 | 未来动作与目的 | 必留实际回执 / 失败处理 |
|---|---|---|
| 0 | 固定 board、旧 boot、endpoint/真实父桥和 subordinate 作用域；停止新提交/自动启动，确认 no-owner。旧 fd/mmap/lease/IRQ session 作废。 | UTC、命令、return code、stdout/stderr hash、boot、owner/driver身份。不要以首先 unbind/rmmod 来释放可能受影响 pages 并追認安全。 |
| 1 | 对旧 endpoint 清 BME，并读真实 Command。随后使用已登记 sysfs bus reset，入口/出口均 BME=0。阻止 reset callbacks 或并发路径重新设 master。 | 清位前/后 Command、reset_method、实际 reset 命令/返回、reset 后 Command；父桥身份、bridge bits及作用域。BME 非0或 reset 失败，停在本步。 |
| 2 | **reboot 前完整加载上述已 qualified V7 recovery bit 到 SRAM**，覆盖旧用户 descriptor/FIFO/AXI 控制状态/guard。使用已有授权 programmer；不以 new candidate 替代，不写 Flash。 | 本次输入 bit 实际 size/SHA、qualified manifest、工具身份、完整 vendor log、单 PG2L100H、return code、program success、最终 DONE；恢复后可访问 config 时记录 BME。未完整成功/DONE 不得进入 reboot 重建验收。 |
| 3 | 保持 no device open/no DMA/no 自动提交，主机 reboot 建立新 allocator/IRQ/driver session。旧 recovery link/guard 可失效，后面会完整替换。 | 实际 reboot action、boot_before、boot_after!=before、after==current、RC/endpoint 发现和驱动身份。只读采集不以 DMA 读状态。不能把 warm reboot 写成已证实物理掉电。 |
| 4 | 等 build03 actual bit、完整物理/时序/route/source 验收及 delivery consumer 通过。新 boot 中建立当前 no-owner/rebuilt preflight；若驱动已设 BME，控制自动路径并清 BME actual readback。 | 新 bit/manifest SHA、真实独立 verifier 输出、当前 boot/driver/owner；preflight accepted 只能由实际证据产出。旧 V7 不是最终交付 bit。 |
| 5 | **仅在第6节启动可行性得到证据支持后**，对已识别父桥 bit6 掩码 assert 并保持，防止最终镜像先 qualified 再被 reset；完成最终 qualified build03 全 SRAM 编程。 | 父桥 word 原值/assert 后值、其它位一致、BME=0、保持期间桥可读及未自动释放的记录；program UTC/return code/vendor success/单链/DONE、实际 new bit SHA。endpoint 在 SBR 下 config 不可读属于待观察情况，不伪造全零 BME读回。 |
| 6 | 用当前父桥 word 掩码 release bit6；按已证实启动时序等待 link/config 可用，实际恢复枚举及驱动 binding。不再安排 finalprogram 后额外 SBR。 | release 前/后 word、UTC/return code；actual link/resource/MSI、0755实际 BDF、loaded build-id、bind 回执。枚举与 binding 不同于旧 sysfs对象仍在；不假定 BDF 固定。失败只记录失败，不用重复 SBR 将故障包装成 PASS。 |
| 7 | 独立审核恢复链、finalprogram、boot、bit/manifest 与枚举绑定；consumer 实际通过后，再按已有数据面授权启动 viewer，采集两个 post-program 原始 XWD/PNG、metadata及运行证据。 | 实际 consumer 输出/返回码、原始截图/hash/UTC、viewer身份/进度、DMA/error及最终运行结论。失败保留原始日志，不 fabric accepted from assumptions。 |

**preflight 的可执行性要在 step4→5 明确核对。** 现有 consumer 要求 driver_ready/exclusive_owner 和 300 秒新鲜度；不能把 held SBR 时不可达的 endpoint 宣称 ready。可在 step4 用真实 recovery 后当前配置建立 preflight，并将 assert/program/release 动作连续留证；主会话须核对实际 programmer 调用是否在此状态接受该真实 preflight、没有打开 DMA 设备或偷偷 reset。若这个调用路径要求 assert 期间重新获得不可达的 driver-ready 证据，则记录该具体接口不兼容，不能改 consumer 或制造 accepted；也不能默默回退为 program→SBR。此项是实际调用边界核对，不新增 idle gate。

每次实际配置读取必须保存原始字节及返回码；不能把全1/短读/失败解析成 BME=0。每个 action 保存 UTC start/end、工具/命令、return code、stdout/stderr及其 SHA256，按同一 recovery session 绑定 board/boot/bit。SBR 保持段另保存 bridge bit6 原值/assert/release 与其它位不变；vendor 段保存 program success 与最终 DONE。独立审查者核对因果时序，而非仅检查附件名称存在。

## 6. 下一步需要解决的有限因果问题

已有“reboot前完整 recovery”的顺序依据足以修改旧报告的窗口结论；最终 held-SBR 不能现在认证。后续工作限定为以下问题，不把它无限扩大为更强 gate：

1. **板级 PERST 与硬核首次启动要求。** 查当前板 M16 的实际网络/拉电平/来源及配置期间状态；查匹配本 IP 版本的官方 power-up/HSST/GTP_PCIEGEN2 初始化文档或明确 vendor 说明，证明完整编程时即使 PERST 高，内部配置初始化与 held hot-reset 输入也允许正常进入 link training。仅 CORE_RST_N 接线、LTSSM 列表或旧正常链路不足。若官方要求 PERST 低脉冲且板上无可控接口，held-SBR 方案在此停止，报告该具体缺口。
2. **实际 RK 父桥保持及新 EP 加入时行为。** 在允许的受控未来试验中证明真实父桥 config 在 held SBR 期间仍可用、bit6 保持，且新配置的 endpoint 尚未先到 L0/runtime 再遇 hot-reset；release 后能首次训练、识别并枚举/bind。不能由桥 bit6=1 单点读回推出整个保持期间 health_n=0。需要匹配实现的文档/时序或受控真实观察；不要求添加 host 可读 AXI idle 寄存器。正式 build03 前可用既有 qualified V7 做同一启动顺序验证，留独立新 receipts，不把试验镜像签作最终交付。
3. **保存配置与 binding 的真实调用链。** 新配置可能失去 BAR/MSI/Command，旧内核对象可能仍存在；审核既有恢复路径是否在 release 后正确恢复/重枚举和绑定、是否有隐含二次 reset，及 step4 preflight 是否能原样供 programmer 使用。保存配置不能在最终启动之后无意触发 reset；新 descriptor/buffer/IRQ 会话只能以新 boot 与新 generation 建立。

这些证据用于判断 held-SBR 这条具体路径可不可执行，**不要求 SBR 证明全 AXI 取消，也不要求 AXI readback/全域 idle 证书**，因为两次完整 SRAM 重载已经分别承担旧 fabric 失效和最终 guard 初始化。初始 sysfs bus reset 的实际返回/BME连续保持记录与主机 boot action仍必须真实，不能从公开参考源码自动补为已执行。

可省去 reboot 的设计讨论不改变本次次序：当前 rebuilt consumer 明确要求 before!=after。本次保留 reboot，不能用 SRAM 重载或 SBR 伪造新 boot，也不为省 reboot 修改合同。

## 最终判定

**顺序审查已给出可推进路径：旧 V7 recovery 全 SRAM 在 reboot 前；最终 new qualified build03 全 SRAM在可验证的 held-SBR 启动边界内。** 原 blocked 的“旧 fabric 自动 BME恢复跨 boot 窗口”可以由前移完整恢复消除。当前仅缺 held-hot-reset 首次启动的匹配硬核/板级依据及实际父桥/枚举/preflight调用试验；同时 build03 final qualified bit仍待产出。这些是具体剩余工作，不是证明必须物理两板掉电或新增 AXI idle gate。

本报告是本地只读审查产物；actual reset/recovery/reboot/finalprogram/runtime 均未在本次执行，状态保持未验收。最终三项交付只能由真实操作回执、原始运行证据和现有 consumer 独立审核完成。
