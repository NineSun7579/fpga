# build03 四路 source 诊断采集协议

本入口是独立上板准备文件；默认离线，未上板，不生成 hardware PASS。
目录为现有 `goal_board_validation_01`（不是新建近似拼写目录）。未修改 build03、生产 DMA helper、主 consumer 或 viewer。

依据：build03 `rtl/v7_sdt_bus.v` 第20、95–124行；`rtl/v7_sfd_candidate.v` 第125–158、188–208行。
旧 `source_diagnostics_bus_candidate/INTEGRATION.md` 地址/lease/epoch合同及
`diagnostic_sync_register_timing_candidate/sim/tb_bus.sv` 四路 acquire、重复 acquire、reset/epoch、低4位地址丢弃测试作为参考；不运行或动态执行 TB。
collector 固定检查 build03 两份实际 RTL、manifest local_hashes 和真实 helper SHA256。

| 项目 | 实际协议 |
|---|---|
| 四路基址 | C1 `0x20001000`、C2 `0x20001100`、C3 `0x20001200`、C4 `0x20001300` |
| STATUS +0x00 | bit0=lease valid，bit1=sticky overrun，bit2=available，bit3=invalid |
| COMMAND +0x10 | 全字1=ACQUIRE，2=RELEASE；写低32位，WSTRB低4位必须全1 |
| INDEX +0x20 | 0..15，写后读回检查；DATA的AR时捕获索引 |
| DATA +0x30 | lease冻结bank的一个word；无lease/invalid/读事务内epoch变化报SLVERR |
| EPOCH +0x40 | 32位会话代数；camera reset使其变化，0xffffffff永久拒绝；全接口reset可归零 |

每操作都是16 bytes DMA，低32位有意义，寄存器间隔16 bytes。上游PCIe FIFO会清掉地址低4位，故 collector 在提交前拒绝低4位非0的地址，禁止+4/+8/+c猜读，禁止合并burst。真实 RTL 没有独立 busy 位或软件 snapshot-request 位；busy=request与ack不相等是源域内部握手。主机等available、执行ACQUIRE、确认lease；重复ACQUIRE不会更新旧lease。本入口遇已有lease直接拒绝，不擅自释放他人lease。

读取顺序：记录E0 → 有界轮询 STATUS/epoch（默认2秒，可设大于0且不超过30秒）→ ACQUIRE → 确认valid且非invalid/available → INDEX0..15逐个写、读回、读DATA → 再确认STATUS/E1 → 要求E0=E1及格式正确 → RELEASE并确认lease撤销和epoch未变。任何epoch/lease变化拒绝整包，不自动重试或跨reset拼接。四路串行，各路16 words内部原子；不能声称四个camera在同一曝光时刻。overrun原样保留，可能由lease读取期间源继续出帧产生，不能等同payload损坏。

| word | 真实宽度、字段 |
|---|---|
| 0 | 32位source_sequence，模计数 |
| 1 | 24位source_bytes（raw_byte_accept与href相与，再延迟两拍） |
| 2 / 3 | 16位href_segments / odd_href_segments，word3包含边界关闭奇数段 |
| 4 / 5 | 24位aligned_pixels（valid_d）/ native_pixels（capture_valid） |
| 6 | 24位valid_vsync_overlap |
| 7 | [15:0]tail_gap_cycles；[16]armed，[17]have_previous，[18]seen_href，[19]tail_gap_saturated，[20]clipped_href，[21]vsync_mismatch，[22]counter_overflow，[23]bad；[31:24]保留0 |
| 8 / 9 / 10 | 24位previous_source_bytes / previous_aligned_pixels / previous_native_pixels |
| 11 | 16位previous_odd_href_segments |
| 12 | [0]start_native，[1]end_native，[2]start_aligned，[3]end_aligned，[4]end_href，[5]previous_start_aligned，[6]previous_end_aligned，[7]previous_bad；高24位保留0 |
| 13 / 14 | 16位previous_href_segments / 24位raw_byte_vsync_overlap |
| 15 | 格式常量 `0x53464401` |

tail_gap是采样cam_clk周期数，自seen_href且href低时累计，href高/新frame边界清零，到65535饱和。其它窄计数为模计数，overflow/bad标志需同时看；不把bytes除以2推导“正常帧”。raw_words/raw_hex/values忠实输出；每行明确 `normal_frames_proven:false`。

## 离线检查与本地测试

在本目录执行：

```text
python source_diagnostic_collector03.py --check
python -m unittest test_source_diagnostic_collector03 -v
```

不传参数等价--check，不导入Linux设备helper、不打开device。测试用显式事务tape验证四基址、16byte对齐、serial INDEX/DATA、epoch变化、lease丢失、invalid、busy/unavailable超时、read/write异常永久停止、位宽/flags解码。它不是RTL镜像、模拟硬件PASS或新驱动。

## 将来在 RK3568 实际执行

先完成真实 accepted build03 bit交付和SRAM烧写，保存receipt和原始cfg/server/client日志。烧写前60秒内在实际RK采集 `/proc/sys/kernel/random/boot_id` 原文，连同host、采集UTC、collector形成 `programBootCapture/v1`；不能事后用当前boot补造旧program boot。保存实际 `programSession/v1` 与raw开始/完成边界。发生冷重启/PCIe或AXI接口reset/重新烧写后必须重新建立会话；epoch相等不能证明跨整个接口reset有效。

由外部独占supervisor在实际运行机器上建立 `sourceDiagnosticSession/v1` gate。gate是外部授权与事实记录，collector不会自动制造gate或accepted=true。部署保持project相对目录结构，包含本collector、纯离线验证依赖、实际固定 `tools/cam3_i2c_pt.py`、原vendor `tools/program_100h_motion.py`、build03两份RTL和manifest；冻结文件保持字节原样。不要把旧board_poke.py导入：它在模块顶层直接open device。本入口复用现有 `cam3_i2c_pt.PciDriver` 的同一固定device、MAP ioctl2、H2F4/F2H5、4MiB TX/RX与RX offset1MiB及16byte读写接口。仅在helper现有ioctl边界检查非零返回，覆盖其初始化原本忽略MAP返回码的缺口，不重写DMA或生产helper。

gate JSON必需：`contract`、`board_id`、`host`（实际hostname）、`boot_id`、`bit_sha256`、`original_log_paths`（cfg_log/server_log/client_log原receipt路径字符串）、`artifacts`。每个artifact采用已有 `{path:实际执行机器绝对路径, bytes:实际长度, sha256:实际散列}`，不能只填boolean；跨Windows→RK复制后只修改gate中的本地artifact路径，delivery/receipt/session原件保持原hash。

必需artifacts：`delivery`（validatedDelivery/v1原件）、`bitstream`（对应实际bit原件）、`program_receipt`、`owner_preflight`（原boardOwnerPreflight/v1）、`cfg_log`、`server_log`、`client_log`、`program_session`、`program_session_raw`、`program_boot`、`program_boot_raw`、`owner_session`、`owner_session_raw`、`owner_dma_boundary_raw`。

`program_boot`字段：`contract:"programBootCapture/v1"`、`collector`、`host`、`boot_id`、`captured_utc`、`raw_sha256`（program_boot_raw为boot_id原文）。烧写前采集；collector验证其时间在实际program start之前60秒内，boot等于当前 `/proc` boot。

`owner_session`字段：`contract:"exclusiveDiagnosticOwner/v1"`、`reviewer`、`board_id`、`host`、`boot_id`、`bit_sha256`、`program_receipt_sha256`、`delivery_sha256`、`collector_sha256`、`supervisor_pid`、`supervisor_start_ticks`（/proc/PID/stat field22）、`captured_utc`、`expires_utc`、`raw_sha256`。创建时间在实际program completion后，启动collector时最多60秒旧，最多300秒有效；supervisor PID必须等于collector实际PPID，start ticks防PID复用。raw文件逐行保留上述身份/散列/PID/UTC `key=value`，并包含：

```text
session_policy=no_other_device_owner_or_programmer_until_collector_releases
```

`owner_session.dma_quiescence_review`还必须包含 `status:"reviewed"`、`reviewer`、`note`、`boundary_kind:"proven_dma_idle"`、`raw_sha256`、`references:[{line:实际行号,text:逐字原文}]`。绑定的owner_dma_boundary_raw必须保留该会话的 `boot_id=...`、`captured_utc=...` 与实际独立DMA-idle证据；collector验证散列和每条review原文引用，不用“没有fd”代替DMA空闲。缺乏真实idle证据则禁止执行；如果必须冷重建，先重建并重新烧写/重新采集program-boot，再建立本会话，不能拿旧receipt跨boot。

supervisor负责先按已审查session protocol使viewer和其它probe完全退出且DMA已quiescent，确认无uncertain owner；全会话禁止其它device opener、烧写和reset，保持当前receipt是最后一次实际烧写。collector用/proc fd实际rdev扫描核验无其它持有者，并非只信exclusive_owner=true；权限不足fail closed。锁 `/run/lock/pango-source-diagnostic.lock` 仅协调遵循同协议的工具，旧viewer不遵循它，不能以flock代替停viewer和外部监督。扫描与open之间不能机械消除不合作程序的竞态，因此外部exclusiveowner协议是必需事实前提。

supervisor直接启动以下命令（不可用后台shell替换PPID，输出目录必须尚不存在）：

```sh
python3 /opt/source03/project/fpga_v8_migration/board_v7/goal_board_validation_01/source_diagnostic_collector03.py --execute --gate /var/lib/source03/session/source_diagnostic_session.json --output /var/lib/source03/captures/source03_run01 --timeout 2
```

以上由root supervisor直接启动；若用sudo，session绑定的是sudo实际成为collector父进程的PID/ticks，需由监督器按实际进程链记录，不能猜PID。命令只是将来执行说明，本次没有运行。采集完成后才恢复viewer，以新的viewer identity/process start采集主consumer证据；诊断metadata应在后续boardValidation runtime_end之前，不能要求诊断进程与唯一viewer同时占device。

任何DMA timeout/异常/非零完成码/缺失读值（包括初始化部分失败）永久停止后续提交。保留driver对象、已有TX/RX mmap、FD与owner lock，忽略SIGINT/SIGTERM/SIGHUP并每30秒sleep；记录failure.json，不允许timeout包装器强杀、close/free、自动重试或退出释放DMA存储。沿用旧 runtime_probe/diagnose 的holdsleeppolicy：只有外部独立证实DMA quiescence/安全重建边界后才处理这个进程；SIGKILL不是正常退出方案。协议失败且所有DMA已明确完成可退出，不发送补救RELEASE；下一会话需处理残留lease/reset边界。每次helper ioctl自身8秒alarm，所以轮询deadline不是中断正在进行DMA的deadline，操作日志可显示正在提交的地址。

## boardValidation/v2 原始来源包装

实际四路成功读取并正常关闭helper后，才生成 `diag1..4.raw.jsonl` 和 `diag1..4.metadata.json`。metadata为 `diagnosticCapture/v1`：source_camera、board_id、host、boot_id、bit_sha256、captured_utc、raw_path/raw_sha256、collector path/hash、gate/source artifacts绝对来源路径和散列、operations日志/hash、helper/RTL hash。`accepted:false`、`captured_pending_review`、`hardware_pass:false`。

在boardValidation/v2 artifacts绑定 `diag1_raw`/`diag1_metadata` 至 `diag4_raw`/`diag4_metadata`；source_diagnostics每路review必须引用其真实raw行的行号/原文并人工review，不能复制collector默认false改成自动accepted=true。metadata只证明本采集记录的一致性，boot/烧写来源和exclusive协议仍依赖独立受信外部采集与审查；source统计本身不证明正常frames、viewer进度、画面或最终硬件验收。
