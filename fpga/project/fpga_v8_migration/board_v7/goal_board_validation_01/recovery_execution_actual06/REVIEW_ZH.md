# actual06 独立执行审查

## 最新真实执行结果（覆盖下文先前连接阻塞的时点结论）

2026-10-07 05:47 UTC fresh SSH 成功；fresh_0_e2cc51ed 保存完整原件，当前 boot dd39b8d1-cf2d-404e-914d-45eb87278794，EP 0002:21:00.0、父桥 0002:20:00.0，无 holders/producer，EP Command 已变为0406，使用真实当前值处理。

第一次执行被 timing_reload 的全局 mutex 占用阻断，无板动作。新副本精确修正 mutex 为 WaitForSingleObject 实际所有权获取，有限等待在 cancel 前；取得统一排他及全机 idle 后，execution_7cf8fef0e319 实际完成：root-only admission；Command 0406→0402；reset_method=bus、真实 sysfs reset 返回、入口出口0402；完整 qualified V7 SRAM；program_board 内实际 verify_delivery 通过；原 vendor receipt run_20261007_134923_163823f6/receipt.json 为 success/sram，全部六 stages 包含最终 DONE 为 true，stage_errors=[]；SRAM后Command=0402，admission再次verify；随后真实 systemctl reboot。

真实新 boot c1500212-6832-4215-a2b2-76b60c8c3858。post-reboot 在 admission owners 扫描时因 /dev/pango_pci_driver 不存在而失败，保留原 rc/stderr，未放宽扫描或把不存在设备认作 drained。后续只读 refresh run_dd34d6efae3f 确认0755:0755 endpoint为空、模块initstate/build-id不存在。只读 post_failure_readonly/current_state 保存全新 ledger/config枚举/模块/dmesg 原件：ledger root:0600 跨reboot存在，producer hash完全匹配，原mode0755、当前0644；未恢复执行位。新boot dmesg明确 PCIe Link Fail, LTSSM is 0x1, hw_retries=0 和 failed to initialize host。因此本次新boot是真实，但 endpoint/driver 重建失败，不能签完整重建或功能正常。

具体新boot失败回执 execution_7cf8fef0e319/post_failure_readonly/reconstruction_failure.json；vendor/bus-reset摘要 actual_summary.json，全部动作command/stdin/stdout/stderr/rc/hash原件保留。未再次reboot/program，未Flash/held-SBR/GPIO144/unbind/rmmod/viewer，未关闭目标；无需追加资格工作。本次停止于真实PCIe link/host初始化阻塞。

审查人：本次 Codex subagent（实际阅读并复核 prepare05 REVIEW_ZH、controller、admission_guard、只读扫描器、refresh03、legacy program_board、vendor programmer 和 new_validate_board parser）。授权来自主会话本次明确指令；本次仅取消旧会话、完整 qualified V7 SRAM、真实 warm reboot、新 boot 只读重建。此审查不签未来 held qualification、candidate 或 board PASS，不关闭主目标。

prepare05 原件完全保留；source_review.json 保存原 SHA256，*.diff 保存实际新副本变化。新目录 admission ledger 为 /var/lib/fpga-recovery-actual06/admission.json，root-only，保存原 mode/hash，执行位只针对经当前 fresh inventory 再确认的 driving-demo ELF。禁止对 actual MP4 进程和 ELF 动作；不发板上进程 signals。active driving producer（含 launcher/supervisor）将记录真实 argv/exe/hash/stat/boot 后阻断，不自动停进程。

实审修正：program 前且 cancel 前先取得 Global\ov56401_PDS_single_instance，确认全机 pds/gui/TA/programmer 等进程为空和本地 vendor 端口可 bind。整个 cancel/SRAM/reboot/重建保持统一互斥，不 reset 后等待工具；legacy vendor 原样保留 idle/scan/Tcl guards，代码不自行获取 global mutex，无嵌套死锁。Command SRAM 后新增实际 BME 校验；完整扫描错误或 holders 阻断；vendor cfg/server/client 原 log 再核验；ledger 持久 fsync 并要求 root-only。SSH异常保留命令与失败回执。未来 held 字段只在原 held 分支检查；actual06 明确拒绝 held/candidate/release 调用。

执行计划只有 fresh SSH 成功、完整 fd/maps/startup 扫描、当前 boot/endpoint/父桥和已审 producer hash 一致后才生成，reviewer 是本次真实 agent 身份。exclusive_operator_control 依据主会话明确独占授权，范围限已审 producer，不能宣称对任意 root/loader 的内核隔离；owner 空不会产生 drained 或 AXIidle 门禁/证书。

program 入口仍为 timing_correction_05/program_board.py，无 CLI 参数，先真实 verify_delivery，再 vendor SRAM only。bit 必须 dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60。本次完整原 receipt、各 stage、final scan DONE 必须成功才填实际 sram_success_evidence 并推进 reboot。失败不自动 reboot。新 boot 必须由有限重连读取得到，SSH断开/超时不算成功。post 阶段仅现有 sysfs/config/driver metadata，不打开 DMA/BAR，不 GPIO144、不 rmmod/unbind、不启动 viewer。

执行入口：python -B run_actual.py --prepare；审查生成的 execution_plan.reviewed_*.json 后，python -B run_actual.py --execute-plan <实际计划>。每次新目录保留 raw command/stdin、stdout/stderr、rc、UTC、hash。实际结果以 actual_result.json 和其下证据为准；本文件本身不声称已执行任何板级动作。

后续最小 held-SBR 工作仍须另阶段主审：核实当前下游内核 remove/rescan/probe/bind 隐含 reset 行为，制定当前 boot/BDF 对应真实枚举/配置资源/MSI/绑定证据；取得 fresh driver 与独立 ownership preflight；仅 qualified V7 做 held startup 资格试验，采样 bit6 不代替首次启动资格。最终 candidate、Flash 与 viewer 均不在本次范围。

## 本次真实结果：连接阻塞，未 cancel

首次 controller --refresh 在连接时 TimeoutError，原件 run_84b95e34c1d3/result.json。之后 run_actual --prepare 三次有限 fresh SSH 重试均在 Paramiko sock.connect 阶段 TimeoutError，各 fresh_*/connect.receipt.json 保存开始/结束 UTC 和真实异常；没有进入任何远端采集命令。Windows Test-NetConnection 的 TCP/22 与 ping 同时失败，该诊断自身达到 40s 上限，不能解释成 RK reboot 成功。

Windows 初始全机 vendor 进程查询实际为空。V7 verify_delivery 已在本机实际运行 rc=0，stdout/stderr 原件存 verify_delivery.offline.*；这仅证明离线 delivery 完整，不代表本次 program 已执行。默认/dry-run、源码语法和封存原 hash 复核结果见 verification.json。

execution_plan.reviewed_blocked.json 是本次真实代码审查结果，reviewer 为本 agent，但 boot/endpoint/parent 明确 null，execution_ready=false；不能用 prepare05 的旧 boot 代替 fresh 当前绑定。该文件因缺少当前绑定会被执行器拒绝。新的 controller 修正现有错误并保留 diff/原 hash，不构造未来 accepted。

本次 admission 未安装/修改，未清 BME、未 sysfs bus reset、未启动 programmer、无本次 vendor receipt/DONE、未 reboot、无新 boot、无当前 driver/config 新证据；prepare05 的旧观察不得冒充 current。没有信号、Flash、held trial、candidate、GPIO144、DMA/BAR open 或 viewer 动作，也没有关闭主目标。

恢复所需前置是已有 RK 地址 192.168.10.203 的 SSH/22 恢复可达，然后重新运行 --prepare 取得完整 fresh scan 和实际 reviewed plan，再执行 --execute-plan。不能在本次 TCP 不可达状态自动推断板状态或跳过 current boot/身份绑定。恢复链完成后才进入上述另阶段 held-SBR 最小资格工作。
