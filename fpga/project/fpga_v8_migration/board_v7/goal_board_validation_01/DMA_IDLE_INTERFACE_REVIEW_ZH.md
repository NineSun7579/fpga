# 烧录前 DMA idle 接口与 session rebuild 只读核查

本报告仅核查本地文件与公开官方接口文档。未连接 RK3568、未打开 DMA 设备或 PCI resource、未提交 DMA、未重启、未启动 PDS/JTAG、未修改源码、helper、冻结 runtime 或 checker。唯一写入为本报告。工程实际目录为 `project/fpga_v8_migration/board_v7/goal_board_validation_01/`，协议实际路径为 `project/DOC/FPGA_RK3568_传输协议_v1.md`。RTL 搜索使用 Python `read_bytes().splitlines()` 和 ASCII 字节匹配，显示时按 GB18030 解码；行号按原始文件计数。Hindsight 服务不可达，本结论不依赖记忆。

## 1. 结论与适用边界

1. **没有找到既有、主机可通过 BAR/sysfs resource 非 DMA 访问的全域 DMA idle 寄存器。** 内部确有 busy、FIFO empty、AXI transaction state 和 PCIe `radm_idle`，但未组成或映射为已验收主机观察接口。不能把 APB 地址当 BAR 地址，也不能经 DMA 读 AXI 寄存器来证明“无需 DMA 的 idle”。
2. **owner04 不证明 drained。** 它明确记录 `dma_idle_proven=false`；无 owner、release 日志、无 timeout、成功 ioctl、软件 flag=0 都不能补齐硬件在途证据。
3. **不支持把物理断电升格成唯一恢复原理。** 官方支持 JTAG 编程与 FPGA 软件复位；既有工程实测记录支持 cfg_program 后 PERST + PCIe 重枚举。完整 FPGA SRAM 重载、RK 重启及真正的 PCIe reset/re-enumeration 可以建立新的事务/驱动会话，旧事务按复位边界作废，而不是追认成功或 drained。无需逻辑上强制用户给两板物理断电。
4. **但“cfg_program 成功 + 普通 reboot + 能 lspci”三个结果本身还不足以证明完整恢复时序安全。** 官方 cfg_program 不承诺 RK 根端口、主机 posted writes 或 coherent pages 的处理；boot_id 变化不证明 PERST 或根端口复位发生。当前缺 RK3568 此固件/内核普通 reboot 的 PCIe reset 时序源码或同次实际记录。不能在本报告中无条件认证这个组合已经结束了两端所有旧事务。
5. 当前 consumer 不包含 `both_boards_physical_power` / `bothBoardsPhysicalPower` 字段。其 `cold_reset_rebuilt` 分支要求实际 action、前后 boot、重枚举和 rebind；本报告不修改、绕过或自动放宽它，也不把普通 warm reboot 填成 cold reset。

## 2. owner04、当前 fixed 驱动与原事故

下文路径简写：`G=project/fpga_v8_migration/board_v7/goal_board_validation_01`，`A=project/fpga_v8_migration/driver_ownership_audit`，`S=project/source`，`V=project/fpga_v8_migration/whole_candidate_v7_route_01`。

`G/current_kernel_owner04.json:2–6` 是 2026-10-06T22:59:15Z 的保存快照，命令为 dmesg/fuser/uptime/boot_id；`exit_code=0`、`dma_idle_proven=false`、`device_opened=false`。stderr 文件为空，stdout 未列 fuser owner。`current_kernel_owner04.txt:1994–2038` 包含多轮 TX/RX 分配与 release；末尾 `2112–2113` 为 uptime 与 boot `dd39b8d1-cf2d-404e-914d-45eb87278794`。它没有采样 hardware busy、tag outstanding、posted-write 队列或 AXI R/B 状态，也没有证明最后一次 release 前硬件已停止写页。

`G/driver_identity_prebuild.json:3–7` 在同一 boot 的较早快照绑定磁盘 fixed 模块 SHA256 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861` 和 loaded build-id `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`。owner04 没有重采 loaded note，故应称“同 boot 较早已绑定 fixed”，不能声称已获得本次实时模块身份。

**fixed 二进制没有可核验的精确源码对应。** `A/README.md:9,15–17` 记录 retained C、migration C 与 fixed ELF 的 provenance 差异；源码原理必须同时标注二进制佐证范围，不能把 migration 的文件名当 fixed 源码证明。

- retained C `A/board_files/000_pango_pci_driver.c:979–1010` 的 open 重置全局状态，release 释放全局 TX/RX coherent buffers。migration C 的对应行为在 `pango_cdev_open:973–985`、`pango_cdev_release:989–1009`。release 没有轮询 FPGA idle/AXI 最后 B 或执行主机 posted-write fence；注释“停止底层逻辑”不能代替硬件操作。
- migration C `:547–548,601–603,618–619,663–665` 所谓 DMA idle 是 `atomic_cmpxchg(g_dma_flag,0,1)` 软件锁/IRQ计数等待。`:1162–1195` IRQ0 清 flag 后还可能启动排队 camera/NPU DMA；`:1212–1241` IRQ1/2 也有自动提交路径。这些状态不是硬件 outstanding 计数。
- fixed 反汇编 `A/003_pango_pci_driver_fixed_20260926_disassembly.txt:345–361` 明确在 `0x5b8` 先读 MSI count，再于 `0x5c8/0x5dc` 写 TOTAL_LENGTH/CMD。这修复了等待基线过晚窗口，**没有新增全域 idle/fence ABI**。fixed 的 global buffers/open/release/IRQ 行为也有该反汇编佐证（`A/README.md:17`）。
- migration C `:1374–1397` remove 先 free IRQ、unmap BAR 等，末段才 `pci_clear_master`；没有调用 `pci_wait_for_pending_transaction`，没有 AXI 退役读回。仅 rmmod/insmod 清软件状态不能认定安全释放或 drained；当前 fixed 的所有 remove 细节未由精确源码认证。

原事故报告 `project/fpga_v8_migration/board_v7/DMA_TIMEOUT_DIAGNOSIS.md:22–25,104–106` 记录第三次观察 `ETIMEDOUT`、原 owner PID2583 保留 fd/mmap，以及 baseline loaded build-id。`:23` 原始错误为 H2F `PCI_DMA_READ ... MSI ... g_msi.count=388,g_dma_flag=0`；`:42–51` 给出了真实二进制窗口与可解释交错，尚非唯一现场根因。`:78–86` 的真实要求是保留可能被写的 pages、停止新提交、建立全域恢复；`:106` 主会话追加“下一次两板完整断电”。这是针对不确定事务的保守恢复处置，**不是经因果实验或官方硬件规格证明只有断电有效**。

## 3. 非 DMA 可观测接口逐项核查

| 入口/信号 | 源码硬证据 | 能证明的内容与缺口 |
|---|---|---|
| BAR1 CMD/HOST_ADDR/AXI_ADDR/LEN | 协议 `:40–63`；`S/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v:187,219,252,287,321,895` | 写描述符入口，低地址写还会产生 restart。没有 BAR1 状态 read mux；不得写描述符作探针。 |
| BAR0/BAR2 读 | 协议 `:63`；`ips2l_pcie_dma_rx_top.v:267–294` | 文档说 RAM 窗而非状态；现 source 的 BAR0 RAM 实例甚至被注释，BAR2 实例为 RAM。不能把零值/旧RAM值解释成 idle，不能据旧文档保证 BAR0 读可成功。 |
| controller APB 0x210/0x220 | `ips2l_pcie_dma_controller.v:844–882` | 可回读 chunk_rem_bytes/active/count，但属于 APB read case；不是 BAR read decoder，active=0 也不覆盖 FIFO/AXI/posted TLP。 |
| APB 可达性 | `pango_pcie_top.v:279–342,404–409`；冻结 V7 wrapper `:407–412` | UART/APB mux 实例被注释；APB 输入接内部 p_*，没有证明可从主机访问，且 paddr 实际只传 `[8:0]`，更不能把 0x210/220 当已可达接口。 |
| PCIe `radm_idle`, `radm_q_not_empty` | `pango_pcie_top.v:632–666`；V7 wrapper `:658–659` | 硬核输出悬空，没有 BAR 暴露；completion timeout/debug 也悬空。即便未来暴露单一 RX idle，也不自动涵盖 AXI 与 TX posted。 |
| PCIe Bus Master Enable | `pango_pcie_top.v:637` 输出悬空 | 配置位可观察，不能证明应用内部没有待提交；该设计未显式把此输出用于用户逻辑 admission。不能把清 BME 等同于已清 posted/AXI。 |
| RX busy/FIFO/AXI writer | `pcie_fifo.v:92–142,189–203,316–437` | 内部有 mrd_rx_busy、rx_empty、writer state；原 source 最终 RX done 检查 empty 不检查最后 B。信号没有 host status 导出。 |
| TX done/AXI reader | `pcie_fifo.v:545–574,675–734` | TX done 是 fpga_tx_clk_en 的 beat 计数；不是所有 posted writes 已到主机、CPU可见的证明。R_IDLE 也是内部状态。 |
| 通用 AXI DMA read | `axi_dma_read.v:92–145` | trans 在末 RLAST 且 len=0 清，burst_trans 在 RLAST 清，cmd_ready 由 trans 派生；只能说明内部命令阶段，不是主机可读寄存器。 |
| 通用 AXI DMA write | `axi_dma_write.v:113–145,253–273,298–323` | trans 由末 B/真实 abort_done 退役；watchdog 不取消已接受 AW，也不伪造 B。尚无整体 host idle 汇总。 |
| PIPE_STATUS/TS3/CAPL/COOP | 协议 `:120–129`；事故报告 `:19,95` | 图像管线/历史时间戳/租约状态，不是PCIe全域idle；AXI窗口访问本身要DMA，不满足本任务非DMA入口。 |

**source 与已烧 V7 不同，不能混推。** 冻结 V7 `V/rtl/fpga_v8_pcie_fifo_h2f_tc02.v:121–126,303–305` 已把末 H2F 退役关联最后 B credit（事故报告`:58–60`），优于 source 的旧 RX done；它仍没有主机非 DMA idle readout，F2H done 也未成为主机 posted-write visibility 证书。本报告不会把旧 source 缺陷冒充当前 V7 故障，也不会用新候选源码证明当前板载镜像已实现接口。

### 标准 PCIe 配置空间与 sysfs 能做什么

官方 Linux v6.1：`Documentation/PCI/sysfs-pci.rst:40–48,69–75` 支持 `config` 与 resourceN mmap（平台可能不支持）；文本 `resource` 只是主机地址清单。内存 BAR 不是可直接 `cat resourceN` 的通用状态 API。resource mmap 是实际 MMIO，需要先确认 read decoder 与读副作用，不能因为绕过 /dev 就默认安全。

`include/uapi/linux/pci_regs.h:531` 定义 `PCI_EXP_DEVSTA_TRPND=0x0020`；`drivers/pci/pci.c:4708–4721` 的 `pci_wait_for_pending_transaction` 读取 PCIe capability 的 DEVSTA pending 位，`:4730–4747` 将它用于 FLR 前等待，超时后仍能进入 reset。故这是官方现成**局部 PCIe pending**观察点，非 DMA、非提交，可由只读 config 或 `lspci -vv` 的 `TransPend` 查看。它不是 FPGA FIFO、AXI R/B、主机 posted-write 队列的综合状态；posted Memory Write 不靠请求 completion 退役。当前板此位是否实际实现且有意义未验证。`TransPend-`、BME关闭、LinkUp、AER无错均不能单独标 `dma_quiesced=true`。不假设该设备支持 FLR；官方 sysfs reset 仅在支持相应方法时存在。

将来另行授权后可以先做以下非 DMA 旁证采集；本次未执行，也不把该清单作为新增更强门禁：

```sh
cat /proc/sys/kernel/random/boot_id
uname -r
sudo -n fuser -v /dev/pango_pci_driver
cat /sys/bus/pci/devices/0002:21:00.0/resource
readlink /sys/bus/pci/devices/0002:21:00.0/driver
sudo -n lspci -s 0002:21:00.0 -nnvv
cat /sys/module/pango_pci_driver/initstate
od -An -tx1 /sys/module/pango_pci_driver/notes/.note.gnu.build-id
sudo -n dmesg
```

BDF须先由0755:0755重新定位，不能假定重枚举后保持不变。`reset_method`/`reset`是否存在只检查文件元信息或读取 reset_method，不写 reset。不得调用 board_peek/poke 或 DMA register-read helper；open 本身有清全局状态、副作用释放风险。

## 4. 完整 SRAM 重载 + RK 普通重启：支持什么、尚缺什么

### 官方及真实执行证据

- 安装版 `C:/pango/PDS_2022.2-SP6.4/doc/Fabric_Configuration_User_Guide.pdf` 第69页表8、第84页 §4 cfg_program 明确支持 JTAG 编程；第38–39页 §4.3.10 与第85页 §9 支持 `cfg_reset_fpga` 软件复位。手册没有给出“cfg_program 等价于主机所有DMA drain”的承诺，也没有理由强制物理掉电。不能把另一个未实测 cfg_reset_fpga 命令换进已验收 programmer。
- `project/tools/program_100h_motion.py:173–192` SRAM 路径为 scan→assign→cfg_program→scan/DONE；`:195–230,317–327` 检查日志阶段、最终目标/DONE和正常退出。`:9–10` 明确不处理 viewer/PCIe。成功 receipt 只证 FPGA 编程成功。
- 真实 `project/fpga_v8_migration/board_v7/run_20261006_141824_27582c99/log/cfg.log:18–35` 为 PG2L100H 单目标、assign、program 成功、DONE=1 和最终扫链。不是 fixture；证明这套 vendor SRAM 接口已经实际工作。没有在这份 cfg.log 中证明 RK reset 或旧 posted-write drain。
- 协议 `:196–203` 实测记录 cfg_program 后 FPGA PCIe 核复位，MMIO正常也可能DMA死锁；必须 PERST + remove/rescan 才恢复。source `pango_pcie_top.v:224–242,556–564` 将外部 perst 经同步接硬核 power_up_rst_n/perst_n，core_rst_n 重置 DMA，`:69` 导出 fifo_pcie_rst。冻结 V7对应 `:228–241,559–567,71`。这提供现有线路与RTL复位原理，无需新硬件。
- 官方 Linux v6.1 `sysfs-pci.rst:91–95` 说 remove 不关电；`ABI/testing/sysfs-bus-pci:70–76` 说 rescan 重新发现已移除设备；`:139–164` 区分 reset_method/reset。remove/rescan/rebind是主机软件会话重建接口，本身不是物理复位或 drain。

### 最小合法方案（未来可执行流程；本次不执行）

目标是**失效旧会话并建立新会话**，旧DMA/lease/COPY不追认成功。现状无idle readout时，不应要求凭空补一个dma_idle证书或要求新硬件。

1. 主负责人先保存同次 boot、owner、module build-id/hash、最近提交方向/地址/长度及异常。停止新的 admission；若仍有不确定事务，保留原owner/pages，不能先kill/rmmod/free，再靠重载补救。owner04已无owner是历史事实，不能倒填为过去释放安全。
2. 使用现有PERST线路和已证明vendor完整SRAM配置路径建立FPGA复位边界；重载范围包括PCIe用户引擎/FIFO、AXI/crossbar/DDR接口，不能只reset一个软件flag或局部writer。主机侧在复位前后的内存复用窗口中必须保证旧endpoint不能重新bus-master到旧地址；不能默认GPIO跨reboot保持。对本机需要负责人验证并记录该时序，使用既有reset_pcie/PERST机制，而不是新增硬件或凭空新增门禁。
3. 做RK普通重启以建立新boot/内核/分配器/IRQ会话，**并确认这一次确实经历根端口/PCIe复位、旧链路关闭与重新枚举**。若板级warm reboot已实际产生此边界，可复用，不必物理电源循环。若只见boot_id变化而未确认PCIe复位，则补现有PERST与官方remove/rescan机制的真实操作记录；不能说普通reboot天然等价于cold reset。当前报告缺该RK固件/内核reset时序的精确源码，所以这是待验收方案，非已认证恢复。
4. 编程与重启后按协议中的**已知板级**复位/重枚举动作重建；文档旧操作如下，只作执行方案的接口依据，不作当前盲运行脚本（GPIO/BDF须确认，需先处理前述owner/pages边界）：

   ```sh
   # 协议第200–201行的既有机制：PERST低0.3s→高，移除旧endpoint→重扫。
   echo 0 > /sys/class/gpio/gpio144/value
   sleep 0.3
   echo 1 > /sys/class/gpio/gpio144/value
   echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove
   sleep 1
   echo 1 > /sys/bus/pci/rescan
   ```

   这两个等待是已记录PERST/枚举操作延迟，不是DMA排空判据。最小恢复不应自动调用旧 `project/tools/board_reboot_bringup.py`：其第22–28行的MAPTEST会open设备并发MAP ioctl，第87–92行在重启后调用它。不能先运行一遍DMA测试当恢复证据。
5. 从新的实际枚举定位0755:0755；重新绑定**已核验fixed**驱动，采新loaded note、disk hash、boot、resource/link/MSI与owner证据。禁止旧owner/旧mmap跨会话复用，旧IRQ计数和租约作废；后续generation按既有持久分配合同处理。先形成reset-rebuilt审阅证据，再进行另行授权的数据面验收。没有恢复后的正确镜像、驱动和独占owner，不能开启consumer execute。

**顺序与consumer限制：** `new_program_candidate.py:490–508,537–548` 在vendor执行前要求owner preflight。若需要一次重载来恢复旧session，应作为主负责人单独审阅的恢复操作，不能直接调用vendor.run或伪造preflight来绕过consumer。随后以真实重建证据申请当前candidate程序消费。`cold_reset_rebuilt`名字和accepted字段需要负责人按现有合同解释/审阅；本报告既不创建producer也不自动宣布warm reboot符合该分支。

局限：新会话可把旧事务按reset丢弃，不能证明它们全部成功完成；可能丢帧/丢旧写。重新配置不保证保留DDR旧内容，更不能复用旧bank descriptor。完整重载解决用户逻辑残留，RK重启解决旧kernel/IRQ/allocator，真实PCIe reset处理link/controller边界，三者不能互相省略或用“等几秒”替代。若现有控制在特殊故障中失灵、RK不恢复或链路无法复位，物理断电仍可作为实际故障处置；不是每次工作的普遍前置条件。

## 5. bothboardsphysicalpower 来源审计与不放宽消费者

已核查当前G全部相关consumer/checker、project/tools、driver audit、source与原事故报告；对本地小型py/md/json按`both_boards_physical_power`、`bothboardsphysicalpower`、`physical_power`以及去下划线/横线的`bothboards`/`physicalpower`字节搜索。**在当前consumer及其本地compatibility checker中没有发现该字段或双板物理电源断言。**不能虚构一个checker行号；若主会话有另一个尚未留存的helper/version，应提供精确path/hash再定责。

实际规则：`G/new_program_candidate.py:498–506` 接受真实idle附件，或action/boot_before/boot_after/pcie_reenumeration/driver_rebind附件；后者要求不同boot且after==current。`G/local_compatibility_check.py:121–138` 测试rebuilt分支和缺action负例，**fixture通过仅证明schema拒绝/接受，非板上reset成功**。`G/PROGRAM_VALIDATION.md:46,50` 不追认旧drain，且明确FPGA SRAM重载不自动等于3568冷启动。

唯一明确“两板完整断电”的原事故文字是 `DMA_TIMEOUT_DIAGNOSIS.md:106` 的主会话追加处置。由该事故确实能推导“必须停止旧流量并建立真实复位/新session边界”，不能推导“必须bothboardsphysicalpower=true”。如果另外的localchecker硬编码物理电源为唯一方案，那会比当前consumer及已核查源码原理更强，需要主负责人依据本报告独立审阅；本次不改checker、不删附件要求、不提交accepted=true、也不把重启伪装断电。

## 6. 文件身份（SHA256，原始字节）

下列路径相对工作区根 `C:/Users/NineSun/Desktop/ov56401/`；简写G/A/S/V与第2节一致。PDF用页码，源码/文本用上文真实行号。报告生成时观察到的hash不意味着任何板端当前状态。

| 文件 | SHA256 |
|---|---|
| project/DOC/FPGA_RK3568_传输协议_v1.md | 625ee1441abaaec442958c0e954cbb73b1727c08a1f0fd7c5f8fe273b1c22104 |
| S/pcie_dma/pcie_fifo.v | c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027 |
| S/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_controller.v | 0ff0f5c28650e8eb91da5bc39a26c6498874cafe0b51ccfa1847872c3cbacc53 |
| S/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma_rx_top.v | 36638d374bcd3b85ed4c94ec236cb2016ac7556aa896490da2ad220041531449 |
| S/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v | 285fa47b5d9df4f35ea8df30053e42f1b230e684675e9940a406b5f89905795e |
| S/axi_dma/axi_dma_read.v | da64a97bbc3950ad0d2fd4032d4e66e54757a2915a3e6ba3081f89bf4b72ce93 |
| S/axi_dma/axi_dma_write.v | b897bdcc7b28c1f91e9dfa7303a81ada24639de80bcb2248c9e3fcf9f234edc0 |
| G/current_kernel_owner04.json | da22c3df380450e53409982fd309528c88921bcc5cd40415b80fe38b96c2bebc |
| G/current_kernel_owner04.txt | a1c91d665f7d3fae64c6f0f74b60c2e8c8c23da838e7dee5a22e1d1ae91393bc |
| G/current_kernel_owner04.stderr.txt | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| G/driver_identity_prebuild.json | 98d6f703b937bbc195b74325c5f87e7e6de8974e0654da19cd5c053d50f25663 |
| G/new_program_candidate.py | 68055c0e96b663fc88480ab3c3785a0392c920692266652daf63236165e04f1c |
| G/local_compatibility_check.py | 58f221db379811c78e4e15d388b9ebabd9eee31c43b0a4fb1cfa39aa7c1bb22a |
| G/PROGRAM_VALIDATION.md | c81bdb73f18289f51adf9028249042984d6479252fab98a6b221797b0879da80 |
| A/README.md | fe3d3b6e4d2120c59229f7261dfba8044c303dea67dbfdecbf3daac82ecd5f3a |
| A/board_files/000_pango_pci_driver.c | b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72 |
| project/migration/RK3568_PG100H-release/RK3568/master/AI_car_pro_npu/driver/pango_pci_driver.c | 5ac2278f5102f942f0c5ae031ba9cd6eafdf7245f6dd67859f2dff9b784f13e1 |
| A/003_pango_pci_driver_fixed_20260926_disassembly.txt | 9ee37e770cf53b905fd7c6d390eacf5731e3a78e89f8bef2f5727a592bfe04e0 |
| project/fpga_v8_migration/board_v7/DMA_TIMEOUT_DIAGNOSIS.md | fe26dc1d7a4aa4790c5b52b63161467438b4a61308c436960ca8f00f6e9d3559 |
| project/tools/program_100h_motion.py | c9719f35b5ef827d04b77b6088ac27ef88e2cea72898461a4cdfb98657e0660f |
| project/tools/board_reboot_bringup.py | e8cb8a3f689f2f24b2d419add355ef6ec034b8187656871c82e29a6410e130fd |
| project/fpga_v8_migration/board_v7/run_20261006_141824_27582c99/log/cfg.log | fbc8405fb1d7a49ba2a5ce7803edb2ffd6de321fc1d294b9aedb2ddbe938ab1b |
| V/rtl/fpga_v8_pango_pcie_top_h2f_rfg01.v | 2a36809233007d09b0f4583bfcaaed4876f56b54fa4802cec36c07edc1225351 |
| V/rtl/fpga_v8_pcie_fifo_h2f_tc02.v | 44c8cb76e5353415d2ee8c204331663f66fc3671158a3389e0d89b5e2a0f246c |
| C:/pango/PDS_2022.2-SP6.4/doc/Fabric_Configuration_User_Guide.pdf | 30d8bc2a1324e10529ecc4390fc6f6f3e0d1964300fda863378cafb692e124aa |

公开官方Linux证据：以tag v6.1原文下载到内存计算hash，未写入工程；它是接口基准，不能代替RK 6.1.99下游固件/驱动实现。

| 官方来源（github.com/torvalds/linux/blob/v6.1/ 下） | 行号 | SHA256 |
|---|---|---|
| [Documentation/PCI/sysfs-pci.rst](https://github.com/torvalds/linux/blob/v6.1/Documentation/PCI/sysfs-pci.rst) | 40–48,69–75,91–95 | ff4ea82463558a50923f3642390d16c6a2d50c6f86c4f34a4d531901aa49a460 |
| [Documentation/ABI/testing/sysfs-bus-pci](https://github.com/torvalds/linux/blob/v6.1/Documentation/ABI/testing/sysfs-bus-pci) | 17–29,70–76,139–164 | 1b101803b09ff805fbd0742e9b3897e0b0e524c70119f3614a25234486d6cdb2 |
| [drivers/pci/pci.c](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/pci.c) | 4448–4455,4708–4747 | fa49971ce6fe0f25ad234f1aef64328adddb4cdaca6081f6665e9c16e7d45d2d |
| [include/uapi/linux/pci_regs.h](https://github.com/torvalds/linux/blob/v6.1/include/uapi/linux/pci_regs.h) | 531 | b65e9aa0b719afa55221c4b0d76620f09c48244e99401428730e3e435f558dc4 |
