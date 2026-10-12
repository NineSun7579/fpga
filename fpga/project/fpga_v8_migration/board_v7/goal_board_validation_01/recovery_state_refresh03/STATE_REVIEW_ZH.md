# RK3568 只读刷新实测

采集主机 192.168.10.203；本地 UTC 2026-10-07 02:20:56–02:21:01。通过既有 project/tools/board_host.py 的 ssh_connect 连接；先读取本地采集接口及既有 receipt，再运行本目录 collect_readonly.py。全部远端命令为读取；未打开 DMA 设备、提交 DMA、写 config/sysfs/GPIO、控制进程、reset/reboot/烧录或启动 PDS。未读取进程环境、未输出凭据。Hindsight 不可达，本结论来自本次保存的板端输出。

| 项目 | 本次实测 |
|---|---|
| boot | dd39b8d1-cf2d-404e-914d-45eb87278794；首尾一致，未建立新 boot |
| kernel / uptime | 6.1.99；72191.78 → 72194.65 秒 |
| endpoint / parent | 0755:0755 = 0002:21:00.0；真实 sysfs 父桥 0002:20:00.0 |
| driver | pango_pci_driver，loaded initstate=live；endpoint driver symlink 与 lspci 一致 |
| fixed 磁盘模块 SHA256 | 0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861 |
| loaded / disk build-id | 两者均 1102cfd04acaeeea21ca4d03fe27ddbb32b7340a；loaded 原始 GNU note 保存在 identity.stdout.txt |
| endpoint Command | 0402：Mem=1、BME=0、DisINTx=1 |
| parent Command | 0107：I/O=1、Mem=1、BME=1、SERR=1 |
| parent Bridge Control | 0000：bit6 SBR=0，未处于保持 reset 状态 |
| link / MSI | endpoint 与 parent 为 5GT/s x2；endpoint MSI Enable+ Count=4/4 |
| owner | root /proc fd 扫描 owners=[]、scan_errors=[]；仅表示采样时未找到该设备 fd 持有者 |
| viewer | PID 14889，comm=detview-hdmiful，exe=/userdata/detview-hdmifull/detview-hdmifull；不证明其画面/进度或不会重新打开设备 |
| AER 配置状态 | 双端 UESta/CESta 所列错误位均为“-”，TransPend-；父桥 RootCmd 三种报告使能均关闭，不能据此证明历史无错 |

本次 dmesg 原始输出共 2238 行。与 PCIe 相关的最近异常是第1897行 `[72.310934] ... invalid prsnt-gpios property in node`；较早第497–498行有 `[5.121386] ... PCIe Link Fail, LTSSM is 0x0, hw_retries=0` 及 `[5.121409] ... failed to initialize host`，第216行有 PHY pipe_grf 查找失败。它们是本 boot 早期记录，不能写成本次刚发生。第155行 IOMMU 的 `invalidation policy` 是信息，不计作错误。

在本次可见 dmesg 中未发现 AER 错误事件、PCI_DMA/ETIMEDOUT 或 DMA timeout/abort 错误；日志可见范围不证明全历史无错误。最近 DMA 生命周期记录为第2218–2221行 `[69143.*]` TX/RX buffer allocation 与 mmap，以及第2222行 `[69178.655290] pango_cdev_release.`。release 不证明硬件 drain。两次 lspci 返回0，但各自 stderr 有 `Unable to load libkmod resources: error -2`，保存在 pci.stdout.txt 内部 commands 对象；外层 SSH stderr 为空。

## V7 recovery 前有限未满足要求

1. 当前是瞬时采样；viewer 仍运行，没有持续停止 admission/自动重开/驱动自动提交的实际 session 证据。下一步由主会话建立并记录恢复期间的持续约束，不能以空 owners 或单点 BME=0 签成 exclusive/idle。
2. 本目录没有执行 reset；需在实际恢复动作中保留当前 endpoint/父桥作用域、入口/出口 BME、reset 命令及返回和回读。Bridge Control=0000 不能冒充已 assert/held SBR。本次亦未刷新 reset_method；既有 bus 方法登记须在动作前确认。
3. 本目录没有重新验证 V7 bit/delivery 或运行 programmer；实际 recovery 必须绑定已 qualified V7 的真实 bit/hash、工具与 vendor 全日志/DONE，并遵循已有审查的 reboot 前完整 recovery 顺序。此次同 boot 采样没有 boot_before/after、重枚举或 rebind action，不能签 rebuilt。

上述缺口不要求凭空制作 DMA idle 证书。最终 build03 held-SBR 启动的 PERST/M16、硬核首次启动与父桥保持/释放可行性，仍按上级 RECOVERY_ORDER_REVIEW_ZH.md 的有限问题单独核实；本次不证明该方案，也不扩大成 V7 recovery 的新门禁。采集证据超过既有 preflight 新鲜度期限后应重新只读刷新。

结论：captured_pending_review；accepted=false、dma_idle_proven=false。本次无远程连接或凭据阻塞。原始 stdout/stderr/command、UTC 起止与 SHA256 在各 receipt 中；子命令原始 stdout/stderr、argv、UTC 与返回码保存在 pci.stdout.txt。manifest.json 保存本目录产物的字节数/hash及校验结果。
