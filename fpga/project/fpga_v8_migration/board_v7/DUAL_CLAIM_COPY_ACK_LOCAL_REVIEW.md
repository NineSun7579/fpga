# V7 RAW+COOP 最小真实验证路径：本地 ABI / visibility 审查

状态：仅本地 review 方案，未实现 provider、未执行板端操作、未修改 driver/生产程序/RTL，未 program。CAM1 delay A/B/A 由主会话负责，本报告不诊断 CAM1。

## 结论

现有 `cooperative_linux_transport` **不能直接进行 production dual claim/copy/ack**：没有 production EvidenceProvider；fixed 模块修复等待基线竞态，但不提供 completion/visibility ABI。root 权限、ioctl 返回 0、MSI count 增加、CPU fence、延时、重复拷贝相同或图像看起来正常都不能替代证据。

**仅 driver fix + 普通 PCIe BAR ordered readback，目前不能认证 CPUOwnedCopy。** H2F 的退役加真实 accepted/readback 可以验证控制操作；F2H 需要证明最后数据已经离开端点内部队列，随后有可验证的主机可见性条件。源码支持无 RTL 的“同一有序 MWr 流追加 marker”候选，但尚未验收。它可解决 visibility，不能自动补出 AXI response / exact bytes。若无法从冻结电路与平台合同独立证明这些剩余条件，应增加 RTL 完成记录并重新编译，不能降低现有 KnownOK 门槛。

## 身份和证据范围

- 用户给定最新 fixed loaded build-id：`1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`。本地解析 `driver_ownership_audit/board_files/003_pango_pci_driver_fixed_20260926.ko` 的 ELF GNU note 得到同一值，SHA256=`0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`。没有远程复核当前 loaded 身份。
- 已读 `DMA_TIMEOUT_DIAGNOSIS.md` 全文。其第102–106行仍记载**较早失败会话的 baseline 身份**；不得用该历史状态覆盖用户给定的新 fixed 身份，也不得用新身份追认旧 DMA。
- 冻结 V7 sbit manifest SHA256=`dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`。本次核验 TC02 FIFO、TC03 DDR adapter 及 MWr controller / TX mux / MWr read controller 的本地 hash 均符合 delivery manifest；project.pds:606/642/650 选择的是 `inputs/source/pcie_dma/pcie_dma_ctrl/` 三个 TX 文件。
- retained C/header 是 source-qualified；不能仅凭 C 推断 fixed ELF 已包含某项新修复。原来的模块身份审计仍适用。

## Production gate 与固定 ABI

`cooperative_linux_transport/transport.hpp:28–55` 要求真实 provider 验证 device/image/platform/receipt、独占静止域、当前 image/decode、fixed ABI、coherent mapping、H2F ordering、F2H visibility。preflight 禁止 device I/O，且在 open 前刷新；证据必须绑定实际 boot/session、物理域与稳定锁。历史 manifest 不能充当 live 验证器。root 可以提供身份、owner、平台配置和 trace，不能因权限高而填 true。

每次 DMA 在实际 ioctl 后还需 `retired && ordered && exact_bytes == requested && receipt != empty`；F2H 另需 `cpu_visible`。payload COPY 还要求 `response_ok`，才会 memcpy 到独立 vector 并返回 KnownOK。`SessionFaultTransport:16` 的 RAW STATUS 读取也要求 KnownOK；即使普通 read16 能返回 DeliveryKnownUnknownResponse，guard 仍会关闭。H2F write16 明确保持 unknown BRESP，可由 stage/acceptance readback 消除控制操作的语义不确定性。

固定 userspace ABI：64-bit natural alignment，DMA_OPERATION 40 bytes，current_len/offset/cmd/ddr/total_length offsets=0/4/8/12/16，data=24、pointers=24/32；ioctl 宏 size 是 int，不是40。MAP=`0xc0045302`，H2F/ioctl READ=`0xc0045304`，F2H/ioctl WRITE=`0xc0045305`；TX mmap offset=0，RX=1048576；各申请4MiB。保留 C 在 DMA ioctl 只读取参数头，成功路径不返回 completion struct（C:562–615、637–682）。因此 `current_len` 也不是返回的完成字节数。

## 缺失信号及谁能补

| 信号/合同 | 现有证据 | host/driver 能提供 | 仍需硬件/平台证明 |
| --- | --- | --- | --- |
| 独占与 session | 全局 buffers/count/flag，open/release 有副作用 | exclusive open、单线程 admission、per-fd allocations、boot/session ID、owner trace、timeout quarantine | 新 session 无旧流量；运行中不能用 count=0 证明 drain |
| 请求身份 | 无 device cookie；IRQ0 消费全局 flag | 软件 request ID、提交前 IRQ 基线、地址/方向/长度/slot、IRQ epoch 与串行 receipt | 严格干净单飞 session 可作受限关联；若需跨 reset/重复旧 IRQ 的硬件鉴别，须 RTL cookie/epoch |
| H2F 退役 | V7 final B credit 后 done，但不要求 BRESP=OKAY | receipt 记录退役、后续 stage/accepted descriptor 读回；保持 unknown response | 不得称 BRESP 已测得；控制语义可由 counters/readback 证明 |
| F2H 完成字节 | FIFO `fpga_tx_clk_en` 计数，不是返回的 actual bytes | 可记录 requested bytes、边界与 chunk 配置；不能把请求长度直接改名 completed_bytes | 最终 AXI beats、TLP payload bytes、last transmit handshake 的绑定证明/记录 |
| F2H AXI 成功 | FIFO 的 axi_rresp 输入未用于 F2H 成功判定/导出 | driver 无法读到丢弃的 RRESP；ID/version/图像/hash 无法补出它 | 控制读可审查 allowlist+endpoint合法单拍路径；DDR adapter:99–101 因 vendor 无RRESP而恒输出OKAY，仍需独立成功合同和协议错误观测，不能声称vendor实际报告了成功 |
| 最后数据先于 MSI | done 在 FIFO 消费计数处；后面仍有 MWr FIFO | driver 可记录 MSI 和执行额外操作，不能观察未导出的 TX queue empty | MWr 最后 tlast/tvalid/tready 在真正 IP 输入处完成，再触发 ordered marker/MSI，或等价的 IP 明确保证 |
| CPU visibility | coherent allocation/mmap；无返回 fence | coherent 属性验证、device marker 后 dma_rmb、独立 CPU copy、receipt | marker 必须在此前所有 payload 后进入同一 TC/ordering domain；RK3568 RC/interconnect 必须保证该 DMA ordering 到CPU观察 |
| idle/安全 close | 无全域 idle ABI | lease readback、已完成 request ledger、禁自动路径、IRQ同步 | posted drain/队列/AXI等均无在途；synchronize_irq 单独不足 |

关键反例：冻结 `ips2l_pcie_dma_mwr_tx_ctrl.v:207–208` 的数据 MWr 是 TC0/Attr0，MSI TC0（top:626）。**这支持链路上的 ordering，却不证明内部 pending MWr 已先交给 IP**。TX mux:180–201 有独立 MWr FIFO；:277–307 的 CPLD 可先于 MWr，MWr 缺 credit 时 MRd 也可被选择。因此普通 host BAR read 的 CplD，或后续 H2F 的 endpoint MRd completion，不能无条件当作前一笔 F2H 的 drain fence。PCIe ordering 规则只约束进入相应 ordering domain 的事务，不能排空未进入它的本地 FIFO。

## 无 RTL 的受限候选：driver 追加同流 readback marker

最小探索方向是新增**单个 composite ioctl/receipt**，由 driver 持有 submission mutex 完成 payload F2H、追加16-byte F2H marker、观察 marker、dma_rmb、返回 receipt；provider 读取真实 receipt。不要由 provider 偷用另一个 fd 或递归调用 Backend，也不能让 marker 覆盖 frame slot。现有 legacy ioctl 不支持这份 receipt；新增接口必须有独立 ABI/version，并保持旧 ioctl 布局。

可将第二笔 F2H 的来源选为稳定、已核验的 ID/version 等只读控制寄存器，目标为独占 marker slot；每轮先在 idle 下把该 slot 写成与预期值不等的 poison，确保本 session 没有早先 marker 在途。第二笔产生的 MWr 必须接在 payload 后面进入同一个 MWr FIFO，且 payload 的最后输出 beat 在启动下一请求前已完整入队；这点不能仅由现有 early done 推定，必须针对 exact TX pipeline 证明。首次控制 DMA 自身也需完成同一 visibility qualification，不能循环假定 provider 已可进行可靠控制读。

marker 检查需精确定义观察哪个字/字节、poison 如何避免旧值、同一 TLP 各字的CPU观察顺序、dma_rmb 和 coherent mmap 属性。只观察低32-bit ID 并不自动证明 marker 本身全部16 bytes已写完。允许把 marker 当作“此前payload的有序可见性标记”与“marker完整DMA退役”区分，但现有 Completion 对所有读均要求 exact bytes，后者也必须有证明。任意 sleep、CPU atomic fence、双读相同值均不够。

该路径不改 RAW/COOP bank、不需要 scratch DDR 写入，可以成为 driver-only visibility 修复候选；**它不是目前可执行的验收步骤**。验收需要 exact RTL backpressure/credit 场景证明、PCIe IP/RC ordering 合同或独立真实 TLP 观察，以及真实每笔 marker receipt。即便 visibility 通过，仍需证明 exact bytes 与 source response，才能置 response_ok/KnownOK。

若这些结构/平台证明无法获得，最小 RTL 方向是导出 per-request cookie/epoch、累计 bytes、sticky RRESP/协议错误、final IP TX handshake/queue-drained 状态，并在该边界后产生同 TC 非 relaxed 的 completion marker（或 endpoint 发 MRd fence、收到CplD后完成）。H2F 保持 final-B 退役并可导出 BRESP。DDR vendor 不存在的 RRESP 不能凭 RTL重新编译变成“真实硬件返回值”；需定义可实现的协议成功合同及错误观测。这种修改需要重新编译/验证/另行烧录，本会话不执行。

## 门槛通过后的最小一对板级测试

1. 由主会话建立干净 session 和独占 owner，记录 loaded module/image/platform/boot receipts，验证4MiB coherent映射及无自动DMA。production provider 的 preflight/completion/close均对真实证据fail-closed。有限测试不与viewer或CAM1试验并行。
2. 一个 Backend、同一 guarded_transport、同一 coordinator；RAW helper 已锁完整操作，COOP 每个公开操作用 with_exclusive_io。RX control=[0,256)，RAW payload=[256,614656)，保留tag到614672，COOP=[614672,1843472)；marker 可在control区单独预留，严禁覆盖[0,16)控制scratch或任何payload。TX控制16-byte upper96=0。
3. 验证 COOP/CAPL ID/version、fault=0、无bound/config/release pending及COOP静止状态；持久分配非零generation，stage/ARM只敲一次，通过accepted generation/count、rejected和STATUS读回确认。generation不是DMA隔离证明。
4. 各claim一次，读取并复核完整descriptor。RAW使用0x114，COOP使用0x30。以generation、sequence、camera、RAW bank/address 与 COOP source_bank/source_address匹配同一源帧；token各自核验，不能假定跨协议token相等。若不配对，保留真实结果，不重试强配；不声称same-RAW。
5. ACK前先完成两个copy_owned：RAW恰614400 bytes、COOP恰1228800 bytes，每笔有request/retirement/exact bytes/response/visibility receipt，copy前后descriptor不变。仅独立vector可交付；DMA永不指向vector。持有两租约直到两个COPY及配对检查都通过。保存descriptor、receipt、payload及hash；hash用于产物身份，不作完成证明。
6. 两者均Owned后各ACK一次：RAW stage 0x138–0x14c，readback后bell 0x150，验证accepted ACK增1、rejected不变、host unbound且release pending清；COOP stage0x40/44/48，readback后bell0x4c，验证HOST_BANK=no-bank、host claim清。不要给COOP虚构RAW才有的accepted/rejected计数。最后以真实全域idle receipt授权close；任一不确定则停止提交，保留owner/fd/mapping/leases与进程，不ACK、不自动release/retry。

本次交付是可review的证据缺口与候选实现边界。当前没有满足production门槛的板端CPUOwnedCopy，也没有dual COPY/ACK通过结果。
