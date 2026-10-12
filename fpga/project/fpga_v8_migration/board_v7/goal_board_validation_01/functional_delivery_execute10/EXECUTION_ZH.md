此目录执行用户已授权的新 functional bit 板级验证，旧报告和构建输入不变。

1. 核对 Win32 PID 44500 的 exe、完整 controller argv、CreationDate，取得 process handle 后再次核对。仅等待此 handle，不轮询构建，不启动 PDS。
2. 退出后读取实际 BIT_MANIFEST.json，调用 check_functional_bit09.check，失败即停止且禁止旧 V7 替代。
3. 取得 Global\ov56401_PDS_single_instance，检查全机工具和 programmer port 空闲；保留 managed producer 的 0644 ledger、无 owners 扫描；清 BME 并读回；发送真实 reboot，核对 boot changed。
4. 以实际新 bit、SHA 调用原 program_100h_motion.run(sram,timeout=300)，保存原厂 log/Tcl/receipt 和全部单 PG2L100H/DONE stages。
5. SRAM 后核对自然 PCI。仅当无 root/EP、正确 platform/DT/driver scope 且 unbound 时一次 bind；已存在 root 时不盲目 bind/reset。必要时用 SHA/buildid 核验的现存 .ko 一次 insmod。核对 Gen2 x2、0755:0755、BAR、pango driver。
6. 依据 ledger/hash 临时恢复 ELF 0755；原 launcher 与 ldd 已实读，无 LD_LIBRARY_PATH 设置且所有依赖已解析。直接 exec 同 ELF，以两阶段各 duration120 运行六路总览和 driving-demo，不传 --video。仅精确拥有的 viewer 子进程可清理。
7. 每阶段按实际 root PID/exe/argv/starttime/window 采集两组间隔10秒的 XWD/PNG及帧日志，保留完整 log、退出码、dmesg。duration 自行退出后扫描释放，恢复0644且保留原 ledger。driving 的 C1-C4 暂停不能当六路证据。
8. collector/runner 永不自动声称视觉 PASS 或 goalcomplete；两模式采集完成后由本会话实际读取图片、帧/模型/motion 记录，给出真实正常、异常及未验证项交主会话审阅。

不 Flash、不 GPIO144、不追加 SBR/形式证明、不修改冻结 IP/旧 FAIL。失败保留 raw 并停止后续，无无限重试。

实际调度入口为 runner_corrected11.py，runner.py 原件保留。修正版在原流程基础上增加重启后的 fresh snapshot 与必要 BME masked clear/readback，并扩大全机 vendor idle 名称检查。原 runner10 仅在尚未生成 checked_bit_handoff、指定 controller 仍存活时，以本会话启动的 PID80400 对应 process handle 取消；其 rc255 是本次等待器替换记录，不是构建或烧录失败。确认证据在 cancel_waiting_runner10_identity.json。禁止重启 runner10 或再启动其他 programmer。
