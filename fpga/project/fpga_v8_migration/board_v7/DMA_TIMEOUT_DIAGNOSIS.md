# V7 第三次相机观察超时：本地诊断与恢复验收边界

本次只分析本地留存日志、ELF 和冻结 V7 RTL，没有连接 RK3568，没有打开设备、发 ioctl、kill PID2583、烧录或改动 V7 构建及生产 viewer。按最新指示停止租约 CLI 实现；没有创建虚构 EvidenceProvider 或 DMA 完成证书。

**结论：当前仍处于 DMA 完成不确定的隔离状态。最优先的具体嫌疑是所加载路径对应的历史 baseline 驱动存在“启动后才取 MSI 等待基线”的竞态。它可以解释 MSI 已处理、flag 已清零，却报等待 MSI 超时的组合。根因尚未在本次加载模块上确认；不得把此解释当作恢复或 COPY/ACK 授权。**

## 原始事实与证据身份

原始证据目录：`run_20261006_134504_c9abdebb/runtime/`。

| 文件 | 本地 SHA256 |
| --- | --- |
| `camera_observation.json` | `addebd93ea16b69a81076e54b97e9604bd588e2fd1bee375cc8a4b41135f2c9f` |
| `kernel_pci.txt` | `180b61ddc6ccb04dad47fbce7841bdcee7a243f01ac0fbe4f013b7af77f48245` |
| `cameras.log` | `99f1ad4536dd5730fd082b8459fef0ad0ad135c11588096ef77b1c047d1f7d69` |
| `probe.log` | `e597be69aaf78b5f6792bb4a3ce50a864b6657bb35be8b8bcfd731921052264e` |

- PCIe 在本次恢复枚举时为 Gen2 x2，FPGA `0755:0755`，驱动注册了 MSI0/1/2（`kernel_pci.txt:1–47`）。这不是超时当刻的链路快照。
- 独占 probe 观察 COOP=`0x434f4f50`、CAPL=`0x4341504c`、版本均为 `0x00010000`、COOP LAST_ERROR=0；RAW STATUS=`0x182`，MANAGER_BANK_STATES=0，ACCEPTED_GENERATION/CONFIG_COUNT=0（`probe.log:1–10`）。这些是超时前的观察，不是全 DMA idle 证明。`0x182` 包含 CONFIG_OK、CONFIG_READY、另一个状态位；ARM 位未置位。
- 两个完整记录的 sample 时间为 1125.969661044 与 1130.975309989，间隔约 5.006 秒。两 bank 最大 tag：CAM1/2 46648→46873、CAM3/4 26650→26779、CAM6 41854→42056；CAM5 3127→3127。不能由这两个 sample 认证持续吞吐率或 RAW/COOP 稳定拷贝。
- 日志中 motion 的 `generation` 1…8 属于相机观察命令数据，不能当作 CAPL 已接受的持久化 generation；RAW probe 显示接受 generation 为 0。
- 第三次观察未形成完整 sample。`camera_observation.json:1–4` 为 `uncertain_buffers_held`、PID2583、`TimeoutError(110, 'Connection timed out')`。用户确认进程保留 fd/mmap 且无新提交。
- `kernel_pci.txt:83` 的原文为：`[1138.961468] PCI_DMA_READ Error: Timeout waiting for MSI interrupt [g_msi.count=388, g_dma_flag=0, g_cam_flag=0, g_cam_done=0, g_ack_num=0]`。

**方向必须按驱动定义解读。** 留存 C 的 `PCI_DMA_READ_CMD`/ioctl4 是 FPGA 读主机，即 H2F 写 AXI/DDR；`PCI_DMA_WRITE_CMD`/ioctl5 才是 FPGA 写主机，即 F2H 读 AXI/DDR。此次错误字符串指向 H2F 路径，不能仅凭“DMA read”称它为 F2H 读失败。相机观察脚本的实际提交源码/最后操作地址未在该 runtime 目录留存；不知道具体是哪个 motion 命令/地址、长度和 ioctl 序号，不作猜测。

## 驱动二进制的具体竞态

证据位于 `../driver_ownership_audit/`。历史 `board_evidence.json:139–167` 将 `/userdata/linaro/projects/fpga/RK3568/pango_pci_driver.ko` 绑定到 SHA256 `78e7c415f83844465e6ba7c7741be7b49e712774f276a7909c60c0ab3903b519`、build-id `2c7d51342cfb0617636ef45eaf4717da86aa8592`。本地 `board_files/004_pango_pci_driver.ko` 与 `002_pango_pci_driver_baseline.ko` 字节完全相同，均为 213368 bytes；本次重新计算 SHA256 确认一致。

**本次 runtime 没有当前 loaded module build-id/磁盘 SHA256，所以这里只证明历史磁盘副本行为。** 之前审计中运行 viewer 时加载的 fixed build-id=`1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`，不能沿用为此次重载后的身份。保留 C 源码的 `old_r` 已在启动前（`board_files/000_pango_pci_driver.c:592–595`）；只读源码会漏掉 baseline 二进制的实际竞态。

本次直接读取本地 ELF 符号表确认 baseline `g_dma_flag=0x890`、`g_msi=0x898`。`002_pango_pci_driver_baseline_disassembly.txt` 提供以下顺序（地址为 ELF `.text` 内地址，不是板端 MMIO 地址）：

| 路径 | 启动相关 MMIO 写 | 解锁与 MSI 等待基线读取 | 影响 |
| --- | --- | --- | --- |
| H2F/ioctl4 | `0xa64`: BAR+0x200 TOTAL_LENGTH；`0xa78`: BAR+0x100 CMD | `0xa84`: 解锁；`0xa88`: `ldr w22,[x19,#0x898]` | 完成 IRQ 可以先于等待基线读取 |
| F2H/ioctl5 | `0x760`: TOTAL_LENGTH；`0x774`: CMD | `0x780`: 解锁；`0x784`: 读取同一 count | 存在同类窗口 |

H2F 等待比较位于 `0xa90–0xa98`，超时取值/打印位于 `0xb1c–0xb34`。本次还检查 ELF `.rodata.str1.8` 偏移 2512，确认该分支字符串确为 `PCI_DMA_READ Error: Timeout waiting for MSI interrupt`。

IRQ0 在 ordinary 状态 1 时把 `g_dma_flag` 原子交换为 0，并增加 MSI count；不会检查本次请求 cookie（baseline 反汇编 IRQ0；留存 C `1165–1207`）。因此存在如下合法软件交错：

1. 本次获得 ordinary DMA 状态，count 原为 387，提交 CMD。
2. 短 H2F 已完成，IRQ0 清 flag 并使 count=388。
3. ioctl 此时才取等待基线 `old=388`。
4. 没有后续 DMA/IRQ，条件 `count != old` 一直为假，超时报 count=388、flag=0。

387 是用于解释的假设起点，日志没有记录本次 `old`，不是实测值。本次本地纯软件交错重放验证：`start→irq→snapshot` 得到 `(count=388, flag=0, old=388, wait=false)`；`start→snapshot→irq` 和 `snapshot→start→irq` 均得到 `old=387, wait=true`。这只证明软件竞态机制可产生该组合，不是板端重现。

已有 fixed ELF 的 H2F 在 `0x5b8` 读取 count（其符号偏移为 `0x98`），再于 `0x5c8`/`0x5dc` 写 TOTAL_LENGTH/CMD，消除了此处“取基线过晚”的窗口（`003_pango_pci_driver_fixed_20260926_disassembly.txt:345–361`）。它仍保留全局 buffers/IRQ 状态，不能视为请求身份、AXI 成功或 CPU 可见性的完成证书，也不能在隔离中直接换驱动。

## V7 RTL 能支持的判断

这里检查的是本次 `receipt.json` 指向的 `../whole_candidate_v7_route_01/` 冻结输入与 RTL。sbit SHA256=`dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`。本次重新计算 top、TC02 FIFO、DMA wrapper、controller、MSI arbiter 五个文件的 SHA256，均与 `delivery_manifest.json` 相符；top 第463行实际实例化 TC02 FIFO。PDS 登记、实际 top 接线与该目录代码用于分析，不修改任何文件，也未运行新的 RTL 仿真。

- `rtl/fpga_v8_cooperative_top_v2_rfg01.v:461` 把外部 `msi_req` 全部绑零。`fpga_v8_pango_pcie_top_h2f_rfg01.v:524–527` 将 DMA MSI 接 vector0。因此冻结 V7 不会由常规相机/NPU外部请求持续启动驱动 IRQ1/2 自动搬运。日志 pending/camera done 均 0 与此一致。驱动仍有自动 DMA 路径，但它不是此次故障首选解释；若存在旧 IRQ/身份错配则仍需排查。
- V7 的 H2F `fpga_v8_pcie_fifo_h2f_tc02.v:121–126` 在 writer 完成、最后 B 握手且 BID=0 后翻转退役 credit；`303–305` 还要求 admission、全部输入字节打包完成、计数满足、FIFO empty 和新的同步 credit 才给最终 `fpga_rx_done`。`fpga_v8_pcie_dma_h2f_rfg01.v:340–342` 将 `~fpga_rx_done` 接 controller busy 输入，controller `978,1024–1028` 据其下降沿发 MSI。因此旧冻结路径“收到 CplD 就发 MSI、先于最后 B”的诊断不能直接套到 V7 的最后 H2F chunk。
- 该 H2F credit 不要求 BRESP=OKAY，属于退役证据而非 AXI 成功。最终仍需有序端点读回、accepted/rejected counters 和同一 descriptor 才能判断 ARM/CLAIM/ACK 是否被接受。
- F2H busy 输入是 `~fpga_tx_done`（DMA wrapper `340`）；FIFO `599–618` 的 done 来自 `fpga_tx_clk_en` beat 计数满足 `total_beats`。这证明逻辑从 FIFO/RAM 消费计数的事件，不能单独证明全部 posted PCIe writes 到达主机并被 CPU 可见。当前 ABI 没有 returned completed_bytes、请求身份或可验证的主机 fence。因此即便修复等待竞态，仍不能直接返回协议的 `DmaResult{KnownOK, full_length}`。
- MSI wrapper `113–129` 将脉冲保持到 grant，故“只有一拍所以必然丢 MSI”不是当前代码支持的判断。`inputs/source/pcie_dma/msi_arbiter.v:91–98` 在 grant 时优先清 pending、忽略同周期新 rise，是应在后续仿真覆盖的边界；没有现场波形，不能认定此处导致这次超时。

## 原因排序与可区分证据

| 假设 | 当前判断 | 将来验证所需证据 |
| --- | --- | --- |
| baseline 完成早于 count 基线读取 | 优先嫌疑；精确二进制顺序存在且能解释 flag0/count388 | 当前 loaded build-id；每次提交前 count、snapshot count、CMD 时间、IRQ0 old_state/count 时间；同一请求顺序 trace |
| 驱动 timeout 清 flag，或旧 IRQ 先消费 flag | 仍可能，取决于当前二进制和真实 IRQ 顺序 | 当前 module 的 timeout 分支反汇编；IRQ0 输入状态；请求身份、reset/IRQ epoch |
| H2F 未完成或 MSI 未到 | 当前数据不能排除；若 baseline 不主动清 flag且没有 IRQ，通常应保留 flag1 | B/credit、controller done、arbiter req/grant、RC IRQ 分段 trace；日志 flag0 不是硬件 idle |
| MSI pending/grant 边界丢失、重复 IRQ | 可测试边界，未证实现场发生 | exact RTL 仿真及 req/grant 波形，一次请求恰好一次完成事件 |
| DDR/链路异常、RX 被旧 posted 写覆盖 | 没有直接现场证据，仍未被退役证明排除 | 非 DMA 依赖的 link/AER/控制器状态，主机写可见性及 old traffic drain |
| CAM5 故障导致无帧 | 不支持作为首因；CAM5 未 ARM，RAW 自由状态为预期 | 恢复后先验证 ARM acceptance，再观察 publication；现在不 ARM |

WiFi power-save 日志与 PCIe 超时相邻只说明时间邻近，没有证明因果。Linux ioctl `ETIMEDOUT` 也不是 SSH 网络超时；板端程序已经收到 errno110。

## 当前隔离与可验证恢复方案

现在 PID2583 是设备 owner；“无 viewer owner”不等于“无设备 owner”。原 owner、fd、TX/RX coherent allocations、mappings、可能 pending 的 H2F/PCIe 事务必须继续保留。不给它增加 probe、MSI wait、重试、ACK、ARM 或 reset 操作。`board_peek.py`/`board_poke.py` 均会新 open；open 清全局状态、release 释放全局 coherent buffers（留存 C `979–1010`），不能拿它们查看当前故障。当前 ABI 无法通过新客户端安全完成恢复。

以下是将来单独恢复工作的验收方案，不是本次执行步骤或已获恢复证明：

1. **保留隔离先取非提交证据。** 另行授权后读取当前 loaded module note/build-id、磁盘 module hash、`/proc/<pid>/fd`/maps、`/proc/interrupts`、链路/AER 和 kernel 日志；不 open DMA 设备。补齐 observer 原提交脚本和最后操作记录。若需要内部 count/flag/CTRL 状态，只能走经过审查、不提交 DMA且不清状态的观测接口；当前没有这样的已验收接口。
2. **建立实际 DMA 隔离及全域恢复边界。** 需要阻止新总线主控事务、处理已发 posted writes/在途 IRQ，同时协调 PCIe controller/FIFO、AXI writer/crossbar/DDR adapter、capture/COOP；保留原 coherent pages 直到设备无法继续写它们且旧写/IRQ已被排空。仅 PERST、root bind、open 清 count、等一段时间、button/重新 program 或 gen++均不是这套证明。具体板级 reset/隔离时序尚未被本次证据验证，不能提供“执行某命令就安全”的承诺。
3. **明确释放权限。** 在可验证硬件 drain/隔离及主机 posted-write/IRQ同步条件成立后，才可协调原 owner 退出并释放 buffers、卸载/替换模块。`synchronize_irq` 只排空 handler，不排空 PCIe posted writes；不能独立授权 free。固定二进制只能作为修复等待竞态的候选。
4. **修复并验证完成合同。** 基线必须在启动前采集；用 request/session/epoch 身份绑定 IRQ 完成，拦截 stale/重复 IRQ，返回完整完成字节数和错误状态；F2H 给出可验证 posted-write visibility/fence，timeout 保留 owner/pages且禁止新 admission。记录 allocation bounds 并防止 camera/NPU 自动路径写入串行 RX slot。IRQ 到达“早于 wait 入队”本身不是错误：Linux wait_event 会重查条件；真正问题是计数 snapshot 在启动之后。
5. **恢复后有限帧验收。** 唯一 fd/唯一后端提交线程；一个 RX slot 逐次使用，只有上一笔确实退役并拷入独立 CPU bytes 后才复用；任何 timeout/异常永久停止提交并保留 fd/mappings/leases。先做 16-byte register H2F/F2H 对照，记录每笔提交/完成/IRQ身份，再做有限 RAW/COOP 帧，并以完整 descriptor 对照源 bank/address/sequence/generation/camera/token。无稳定拷贝证据不得 ACK，不用 FPS 作为通过条件。

## generation 与寄存器/ARM/租约最小验证

可复用 `../epoch_allocator/allocate_epoch.py:111–121` 的 `allocate(journal, stable_physical_domain)`：跨进程锁、journal 与目录 fsync、单调非零 32-bit、耗尽拒绝回绕。journal 必须已经按独立可证实的已用上界配置且未回滚；本次不能初始化为 0、随机 generation、借用 motion generation 或重复使用失败分配。分配新数值不退役旧 DMA，也不替代全域恢复。

当前状态下最小验证仍然被隔离阻挡。将来先有恢复边界和可靠控制事务退役/有序读回，才可进行下面的有限观察；此流程可以验证寄存器与租约，不认证 payload COPY：

- 物理地址公式为 `0x40010000 + 4*local`（`cooperative_host/coop_host_protocol.hpp:39–41`），每次完整对齐 16-byte AXI beat；upper 96 bits 必须为零。
- 检查 COOP/CAPL ID/version；CAPL STATUS CONFIG_OK/CONFIG_READY、BANK_STATES=0、无 host bound/config/release pending；同时确认 COOP lease/work quiescence。单独 CONFIG_READY 不能证明 PCIe 全域 idle。
- 持久分配 generation；记录 old accepted generation、accepted config count 与 rejected configs；stage `local0x10c`并读回，ARM `0x110`只敲一次。观察 accepted generation 匹配、accepted count 恰增1、rejected不增、ARM/CONFIG_OK且无 fault/pending，判据对应 `capture_host/capture_host_protocol.hpp:127–174`。
- 有 offer 后只 CLAIM 一次 RAW `0x114`与一次 COOP `0x30`，记录请求 bank、accepted/rejected计数和完整 descriptor，再次读回确认 bound、token/sequence/generation/camera/address/length稳定。若两者属于不同帧，只报告不配对，不通过 ACK/重试强求同一帧。
- **到 lease 观察为止保持 owner/租约，不 ACK、不退出。** RAW 614400 bytes / COOP 1228800 bytes 的 COPY/ACK还需要独立的完整 DMA及稳定 CPU拷贝证明；当前 driver 成功值不满足该条件。保持占用是最小观察方案的明确结果，最终释放也需上述恢复边界。

本次验证范围：原始 JSON/日志、两个 ELF 的字节身份与符号表/字符串/既有反汇编、冻结 V7 的实际 MSI 接线和 done 判据、纯软件竞态交错。本次未获取新的板端证据、未验证恢复成功、未新增或运行租约 CLI。

## 主会话追加的只读身份确认

`run_20261006_134504_c9abdebb/runtime/loaded_identity.txt` 现已保存当前模块 GNU build-id `2c7d51342cfb0617636ef45eaf4717da86aa8592`，与上述存在启动后 snapshot 竞态的 baseline ELF 一致。磁盘默认模块 SHA256 为 `78e7c415f83844465e6ba7c7741be7b49e712774f276a7909c60c0ab3903b519`；fixed候选磁盘 SHA256 为 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`。PID2583 的两个4MiB映射及fd仍在。

这确认当前驱动含该竞态，但没有该失败请求的时间trace，仍不能唯一确定现场根因。当前不释放buffers、不卸载模块、不提交新DMA。下一次验证应在两板完整断电停止旧流量、重新建立硬件session并重新加载V7后，使用已核验fixed候选模块；同时记录每次DMA的方向/地址/长度和最后操作，避免再次缺失现场定位。冷启动是实际恢复手段，不是对旧租约完成或DMA成功的追认。
