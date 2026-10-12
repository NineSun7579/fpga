# prepare05 实际准备交接

本目录全新创建；仅 SSH 只读刷新和本地 dry-run。没有启动 PDS/programmer，没有烧录、reboot、信号、chmod、远端文件写入、PCI 配置写入或 DMA/BAR open。执行代码只为主审以后工具空闲时使用，本子任务未运行任何 `--execute`。没有生成独立 accepted、drained、AXI-idle 证书；会话取消设计仍是完整 qualified V7 SRAM + 真实 reboot。

## 实际状态和原始证据

最终只读刷新在 `run_b115656b2183/`：每条 SSH 命令都有 `.command.txt`、原始 stdout/stderr、rc、UTC 和 SHA256；`startup.stdout.txt` 内嵌命令也保留 argv/rc/stdout/stderr/hash。PCI config 原始前64字节以 hex 和 hash 保存，读取对象仅 PCI config/sysfs 元数据，没有读取 resource0/BAR 或打开 `/dev/pango_pci_driver`。`verification.json` 重新校验全部外层命令回执 hash/rc。前面三次刷新原件也保留，不覆盖历史。

- host 由 refresh03 使用的 `project/tools/board_host.py:board_host/ssh_connect` 原样解析，要求 `192.168.10.203`；hostname=`linaro-alip`。不猜凭据、不打印 helper 内容或 secret。helper SHA256=`632aad99cad8dc62ab03d1659af48e75d651b98c9034a870d290bd92ad0d43b3`。
- boot=`dd39b8d1-cf2d-404e-914d-45eb87278794`，采集前后相同。endpoint=`0002:21:00.0` / 0755:0755 / driver=`pango_pci_driver`；真实父桥=`0002:20:00.0` / RK3568 / class=060400；该父桥下实际 endpoint 在 PCI raw/sysfs 路径中留存，未假定 BDF 永远固定。
- endpoint Command=`0402`，BME=0；父桥 Command=`0107`，BridgeControl=`0000`，SBR=0。reset_method=`bus`。config64 SHA：EP=`8f4a588de0e6627b3bfb5641d32f2baeed3e8394216c4f78abc4d4cba6af7d3c`，父桥=`310836e195f4299229e84035cb6ab966d2c819000d37e2061657cbf5e8bee38b`。
- 当前 fd/mmap holders 为空，扫描无错误。这是观察值，**不是 drained，也不是持续 stop-admission 已建立**。
- PID14889 的实际 argv 为 `/userdata/detview-hdmifull/detview-hdmifull --model MVP_rk3568_int8 --video /userdata/linaro/detview-video-work/media/VID_20260912_151339_480p30.mp4 --video-loop --fullscreen --no-tracking`；ELF SHA=`ad4f43b9640a021bdbcb8e206986a84d2ffdf3f39eb52e97b482b014a7bd7584`。PID14911 是它的 ffmpeg 子进程。两者没有设备 fd/mmap；本轮未暂停它们，未来 helper 也不发信号。hold04 的失败身份没有被追认成成功。

## 真实自动启动/恢复路径

完整 launcher 原文在最终 `startup.stdout.txt` 的 cat 命令结果：`/userdata/detview-driving-demo/run_driving_demo.sh`，SHA=`b38db583e900f8a095d1c9e1985c44d8d181c2908bf5326932e67d9a6bcc5108`；默认 ELF=`/userdata/detview-driving-demo/detview-driving-demo`，SHA=`72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703`。

实际链是 `bash launcher start/restart → setsid bash launcher supervise <log> <args> → APP --driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo <args>`。非零退出最多重试3次、退避1/2/4秒。状态在 `/run/driving_demo`（fallback `/tmp/driving_demo`），launcher 会读回 `launch.args` 并保留之前的视频输入。当前 app.path 指向真实 driving ELF，launch.args 是 `--video <同上MP4> --video-loop --driving-video-padded480`；没有 app.pid/supervisor.pid，proc 未见对应进程。不能把此残留状态当成活的相机 viewer。

已扫描 systemd unit/config、systemctl 全部 units/unit-files、各实际 home 的 autostart/systemd-user/xfce/session、/etc/xdg、lightdm、cron、rc.local、限定层级 /userdata /opt /usr/local/bin launcher。未发现 driving-demo 的 systemd/autostart 注册；rc.local 原文没有 demo 启动。该结论限定于扫描范围；不把不存在的 unit 编造成 `systemctl stop driving-demo.service`。真实可见自动恢复来源是上述 supervisor，任意特权手动启动/替换 APP 的通道仍须主审独占控制。

不要运行 launcher `status` 来冒充只读：它在分支前可创建状态目录和锁文件。也不要直接调用 `stop`：其 owned_process 只核对 exe/starttime，未核对完整 argv。若以后建议 hold 活进程，必须重新采集并精确匹配 boot、exe/hash、完整 argv、stat starttime；本脚本遇到运行中的 producer 直接阻止执行，不自动 STOP/TERM/KILL。GPIO144 完全排除。

## 可执行入口与顺序

在本目录运行（使用现有 Python 环境）：

```powershell
C:\Users\NineSun\anaconda3\python.exe -B controller.py
C:\Users\NineSun\anaconda3\python.exe -B controller.py --dry-run
C:\Users\NineSun\anaconda3\python.exe -B controller.py --refresh
```

默认和 `--dry-run` 不加载 SSH、不调用 subprocess/programmer，只读本地 V7 bit 并生成新的本地 recipe；真实输出保存在 `default.stdout.txt`、`dry_run.stdout.txt`。`verify_prepare_readonly.py` 在禁用 connect/subprocess/execute 的条件下实际运行这两个入口并校验 rc=0、board_changed=false、accepted=false，不是示意输出。`--refresh` 仅执行已有 refresh03 只读命令和本目录只读 inspector。

最终刷新生成 `run_b115656b2183/execution_plan.prepare.json`，实际绑定 boot/EP/父桥/producer ELF hash/V7 hash，reviewer 与未来审核字段保持空/false。后续主审将具体审核结果和实际回执路径填入**新副本**后，逐阶段运行：

```powershell
python -B controller.py --execute --execution-plan <reviewed-plan.json> --phase cancel-before-reboot
python -B controller.py --execute --execution-plan <same-reviewed-plan.json> --phase reboot
python -B controller.py --execute --execution-plan <same-reviewed-plan.json> --phase post-reboot
python -B controller.py --execute --execution-plan <new-boot-reviewed-plan.json> --phase held-v7
python -B controller.py --execute --execution-plan <new-boot-final-reviewed-plan.json> --phase held-candidate
```

每个执行阶段都有本地排他 execution.lock；涉及 programmer 的阶段先检查全机 PDS/programmer 空闲，再调用保留原 guards 的入口。不修改另 agent 的输入，不自动排队或 daemon 执行。

1. `cancel-before-reboot` 首先复核 boot、0755:0755 和真实父桥。`admission_guard.py` 对实际审核的 producer ELF 清除执行位，原 mode/hash 写入 root-only `/var/lib/fpga-recovery-prepare05/admission.json`，因此跨 reboot 保留；不改 ELF 内容、不发信号、不动 actual MP4 ELF。其 verify 要求 inventory/hash/mode 全部匹配，并重新完整扫描 fd/mmap。**这闭合的是已审核 managed producer 路径，不是对任意 root/动态 loader 的内核强制隔离。** 主审独占操作、禁止 APP override、新 ELF 部署和新提交是此方案明确的运行前提；新增 producer 必须补进审核 inventory，不允许默默沿用旧清单。
2. 实际命令由 controller 留证：`setpci -s <EP> COMMAND` → `COMMAND=0000:0004` → readback；拒绝失败/短读/ffff；核对 reset_method 恰为 bus；向实际 `/sys/bus/pci/devices/<EP>/reset` 写 `1\n`；入口和出口均要求 BME=0。不 unbind/rmmod，不将空 fuser 当 drain。
3. 调用 `python timing_correction_05/program_board.py`，无参数；该入口先执行现有 V7 verify_delivery，再 `vendor.run(mode='sram')`。controller 再绑定 stdout 唯一 receipt 与原 receipt，解析原 cfg log 的完整 vendor stages/DONE，保存所有 log hash及本次 boot。V7 bit SHA=`dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`，size=3,791,112；manifest SHA=`cf7b255563d1e0d64c5dad0693e4c4e91d25c48efe50b5c83190d7ce89bbbafb`。SRAM后再次实际读取 Command并验证admission。**不调用新candidate consumer来装载V7，不改Flash。**
4. `reboot` 要求 `sram_success_evidence` 指向上阶段真实 `qualified_v7_sram.binding.json`，检查 bit/boot/原receipt/log hashes后才发 `sudo -n systemctl reboot`，保存实际 rc；SSH断开/失败不虚构 boot_after。`post-reboot` 用同一旧boot计划重新连接，要求 actual boot改变、admission ledger仍生效，执行全新只读刷新；生成 `rebuilt.prepare.json`，不制造 cold_reset accepted。实际 reboot是warm reboot，不称物理掉电。
5. 新boot计划的 boot_before/EP/父桥从 post_reboot 刷新取值；post_reboot_evidence 指向刚生成的 rebuilt.prepare.json。先做 qualified V7 held-SBR trial：入口实际清BME/readback；父桥 `BRIDGE_CONTROL=0040:0040` 掩码assert，只改bit6；250ms间隔实际读取并留每次命令/rc/hash；完整V7 SRAM；实际确认仍assert；`BRIDGE_CONTROL=0000:0040` 掩码release。采样只证明采样时的bit6，不证明整个间隔health低，也不代替板级首次启动资格。
6. release 后调用计划中具体 `enumeration_command`、`driver_binding_verify_command`，再全新只读刷新并保存实际 config/resource/MSI/driver身份。它们当前刻意为空，因为尚未证实当前下游内核的保存配置/重枚举/绑定调用会否隐含二次 reset。填入只读 lspci 不能假装完成恢复；旧 sysfs 对象仍存在也不能签作实际重枚举。可供现场试验的具体写入口是 endpoint `remove`、其真实父桥 `rescan`、驱动 `bind`，必须针对当前发现的 BDF 和下游驱动行为审核，不自动用全局 rescan或finalprogram后SBR兜底。
7. `held-candidate` 先在assert前调用现有 `new_program_candidate.verify()` 与 `verify_owner_preflight()`，原样核对实际 independent preflight；随后assert并调用下述真实 session wrapper，再release/枚举/绑定。要求真实独立V7 startup qualification结果，不能从bit6采样自动生成accepted。不用最终候选bit替代旧会话取消镜像。

## 既有 consumer 的字段与 CLI 边界

| 入口/字段 | 实际来源与调用边界 |
|---|---|
| `program_board.py` | 无CLI参数；legacy V7独立delivery verifier + vendor SRAM。没有 owner-preflight/session CLI；其成功receipt仍 `board_operation_verified=false`，不能冒充最终board PASS。 |
| candidate离线检查 | `python -B new_program_candidate.py --check --manifest <actual-manifest>`；只跑现有build/route/timing/source验收。 |
| actual program session | `python -B capture_program_session.py --execute --manifest <actual-manifest> --owner-preflight <actual-preflight>`。wrapper先SSH捕获boot/hostname/UTC，再调用 `new_program_candidate.py --execute --manifest ... --owner-preflight ...`；绑定唯一新 candidate_run 原receipt、三份原log和cfg parser，输出 programSession/v1 或 failure。 |
| preflight关键字段 | 现有 `verify_owner_preflight` 要求 contract=boardOwnerPreflight/v1、真实accepted/reviewer、manifest/bit SHA、identity_matches_baseline/exclusive_owner/driver_ready=true、captured_unix距执行0..300秒；这些由真实独立review提供，prepare05不填。 |
| preflight artifacts | identity=baseline与本次board身份原件；boot_current=新boot原文；driver_current=本次loaded build-id/initstate及实际绑定；ownership=本次fd/maps/producer admission证据。每个artifact按既有bound(path/bytes/sha256)结构绑定。 |
| rebuilt分支 | boundary_kind=cold_reset_rebuilt，cold_reset_rebuilt=true；cold_reset_action=本次reset/fullSRAM/reboot因果链原件，boot_before/after是实际单boot_id原文，pcie_reenumeration/driver_rebind来自实际动作回执；before!=after且after==current。warm reboot/中间SRAM不会自动认证该分支，仍交独立审查。不要选 proven_dma_idle 来绕过。 |
| held-SBR下preflight | 在assert前取得fresh driver_ready证据；consumer在held期间只验证原文件与hash/300s，不重新openDMA或probe endpoint。长时间完整delivery verification可能使preflight超时；失败保留held状态，不能改消费者时限或伪造新captured_unix。 |
| 运行consumer | `python -B new_validate_board.py --evidence <actual-boardValidation-v2.json>`；actual programSession/bit/boot/原截图及各路运行证据必须匹配，reboot分支仍要求真实boot与枚举/绑定原件。prepare05不产生运行evidence/PASS。 |

## 退出与恢复策略、有限不兼容

任何身份、holder扫描、admission、BME、reset rc或vendor stage/DONE失败立即停止，不进入下一阶段；不自动继续reboot、开启viewer或回滚Flash。admission清执行位后异常仍保持ledger，恢复必须对照原hash/mode，用helper的显式release且在主审验收后执行；本轮没有安装ledger。已有ledger不会重写，需verify。execution.lock遇到进程异常死亡可残留，先核对PID和原日志再移除，不能自动夺锁。

SBR assert后任何程序/采样/consumer失败保留assert和admission，避免失败自动release导致旧/半配置用户逻辑启动。主审可用 `--execute --phase release-sbr --execution-plan <同boot真实父桥计划>` 明确release；此路径允许endpoint不可达，只核对boot/实际父桥class/ledger，再掩码清bit6；release不是program或runtime通过。若bridge本身不可读，停止并保留原始错误，不碰GPIO144、不乱写全word。

剩余事项限定为：held-hot-reset对当前IP/板M16首次启动的实际资格；下游内核完整配置后恢复资源/MSI/枚举与绑定是否引入隐含reset；新qualified候选bit和真实独立preflight/acceptance。已有 V7 程序缺少candidate session接口，因此V7 trial保留独立legacy原receipt+controller binding，不能伪造programSession/v1。执行位admission只覆盖审核inventory，需要主审独占所有生产者入口；这是明确范围，不是声称内核绝对封锁。没有增加AXIidle/readback证书。

本目录最终代码SHA256及全部产物清单见 `manifest.json`。Hindsight不可达；以上结论均来自本地源码及本次SSH原始证据。

供主审核对的 release 后枚举候选**实际命令**如下（本轮未执行，不能直接签安全；使用新boot实际刷新所得BDF替换）：

```sh
# 当前已发现的对象；必须先证实此下游remove/rescan/probe链没有破坏guard的隐含reset。
printf '1\n' | sudo -n tee /sys/bus/pci/devices/0002:21:00.0/remove
printf '1\n' | sudo -n tee /sys/bus/pci/devices/0002:20:00.0/rescan
sudo -n lspci -Dnn
# 重新按0755:0755发现实际BDF，不能假定仍为21:00.0；已自动绑定则不重复bind。
readlink -f /sys/bus/pci/devices/<actual-rediscovered-BDF>/driver
# 仅在确认未绑定、驱动与reset行为审核通过时：
printf '%s\n' '<actual-rediscovered-BDF>' | sudo -n tee /sys/bus/pci/drivers/pango_pci_driver/bind
sudo -n lspci -s <actual-rediscovered-BDF> -nnvv
od -An -tx1 /sys/module/pango_pci_driver/notes/.note.gnu.build-id
```

这些命令是具体待试验路径，并非已通过的调用链；因此生成plan不预填它们。若该链隐含reset导致guard fault，停止记录失败，不能自动重复SBR或当作运行正常；需调整经过资格验证的枚举启动顺序后再实现，不修改consumer契约。
