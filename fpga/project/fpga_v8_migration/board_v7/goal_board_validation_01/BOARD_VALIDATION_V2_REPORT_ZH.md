# 板端验收 v2：离线实现与后续实采要求

当前结论：仅离线验收能力已完善，**没有实际烧录成功或板端运行正常的验收结论**。`board_validation_v2.prepare.json` 的 accepted=false，所有缺证项 pending；必须被拒绝。旧 boardValidation/v1 不再能完成 final scope，可归档为历史非最终评审。`new_validate_board.py` 不连接 RK、不启动 viewer、不调用 programmer/device。没有修改 frozen runtime、producer、program consumer 或旧 device helpers。

## 已实现的可核验检查

- 重读实际 vendor 的纯 `parse_log`（AST 只提取 TARGET/ERROR/parse_log，不 import/run vendor）。cfg 的六项 stage 必须和实际 receipt 一致、全成功；server/client 原始日志不能包含 vendor 已定义的错误。receipt 必须是 SRAM/PG2L100H、check_only=false，且绑定 candidate、bit hash/bytes、delivery、owner preflight、programmer hash及实际 log 路径。
- 当前 `new_program_candidate.py` receipt **没有完成时间戳**。保留其真实字段，新增 programSession/v1 和原始时间/hash文本边界，不凭手填 timeline、文件 mtime 或旧 run 目录推断完成时间。旧 vendor 若有 updated，必须提供明确 receipt_timezone，并落在采集时间边界内。
- 至少两组真实 post-program PNG + original XWD + `capture_rk3568_screen.py` 原 schema metadata。三个文件各自 hash/bytes 绑定。重读 XWD header、完整 payload、width/height/depth、byte order/stride/masks，将原始像素转换后与 PNG 逐像素比对。要求 depth=24；**storage bits_per_pixel 可为 24 或 32**。PNG 的 RGB 三通道不是判定 XWD 存储位数的依据。两次时间、原始 XWD 必须不同，且落在同一 viewer 身份采集窗口。
- `/proc/PID/stat` starttime + btime + CLK_TCK 计算 viewer 实际起点，须晚于烧录完成；前后 snapshot PID/starttime/exe/ELF hash、boot、machine-id、原始 NUL argv、实际模型路径/hash保持一致。另绑定 current_viewer_readonly03 的真实 ELF/source identity 和 current_model_identity03 的原始 sha256sum schema；不声称 source 与 ELF 可复现编译对应。
- 日志使用真实 `journalctl -o json` 身份字段 `_PID/_EXE/_BOOT_ID/__REALTIME_TIMESTAMP`，MESSAGE 保留 current `main.cpp` 的 `[capture] camera=… delivered_fps=… tag_advance_rate=… read_ms=… frame_dma_ms=… copy_ms=… unstable=…`。每路至少两条不同时间、正采集/标签进展、无 unstable；主四路日志必须跨越两次截图且落在前后身份窗口内。0 fps、错身份、越界时间、recover/timeout/stale/失败 ioctl 均拒绝。模型必须有实际 `[model] path OK …` 或 `[rotate-load] path OK …`。
- 六 camera observations 都保留 scope。driving demo HDMI 默认四相机，**不要求一张画面六路同时出现**。C5/C6 可用之后的 supplemental capture session，每个单独绑定 argv、真实 /proc 身份、时间和 journal；不能将主 viewer 的 checkbox 借给补采进程。
- 四 diagnostic source 逐路需要自己的 raw log、diagnosticCapture/v1 metadata（source_camera、board/boot/bit、captured_utc、raw_sha256、collector）、原始行引用和 reviewer 的 source 解释。没有已验证的实际诊断寄存器输出 schema，故不编造 counter parser 或自动硬件通过；缺日志/来源映射保持 pending 并阻止 final。

## 必需 raw files 与合同

所有 artifacts 条目必须是 `{ "path": "实际绝对路径", "bytes": 实际字节数, "sha256": "实际64位hex" }`，不能填模板占位。主合同明确列出必需项：

1. 当次 validated delivery、当次 accepted owner preflight、实际 success receipt、receipt 指向的 cfg/server/client 三日志；program_session.json 和 program_session.raw.txt。
2. baseline_identity 原文件、viewer 前后 /proc snapshot、完整 viewer journal（从 viewer start 至 identity_after）、前后 driver 原始日志；current ELF、main.cpp、readonly identity、current model readonly identity。
3. shot1/shot2 的 PNG、原 XWD、原 metadata，不能复制 baseline、修改 captured_utc 或转换成“成功截图”。建议另保留两次 capture 命令的原始 stdout/stderr/exit/time记录供 reviewer 检查采集来源。
4. C1–C4 的原始诊断采集日志与逐路 metadata。metadata 形式：`contract=diagnosticCapture/v1, collector=<实际采集者>, source_camera=<1..4>, board_id=<当次machine-id>, boot_id=<当次boot>, bit_sha256=<当次bit>, captured_utc=<带时区实际采集时间>, raw_sha256=<对应raw文件hash>`。这是采集绑定 wrapper，不是假称已有驱动输出 schema。
5. 如补采 C5/C6，在 artifacts 增加 supplemental_identity_before/after 和 supplemental_journal；在 supplemental_capture_sessions 添加 `{expected_runtime: <该次实际argv；其余board/boot/exe/hash/models同主session>, identity_before: <artifact key>, identity_after: <artifact key>, journal: <artifact key>}`。capture_observations 的 journal 指向对应 session。补采允许单选/不同布局，只要实际日志证明相应 camera 进展；各 session 必须在主session结束之后。
6. 如发生冷复位：cold_reset_action、boot_before、boot_after、pcie_reenumeration、driver_rebind；新 boot 必须对应 current identity，不能将复位前 runtime 日志和新 boot 混用。

每条人工 review/capture observation/diagnostic source 必须为 `status=reviewed`，有实际 reviewer、note、references。引用格式为 `{artifact:<key>, line:<1-based原文件行号>, text:<该行完整原文>}`；脚本逐行复核，不能只放 True。camera references 至少两条该路实际 journal JSON 行。visual_normal 还须 `reviewed_png_sha256` 按 screenshots 顺序覆盖全部图片。

## 后续实际采集步骤（本轮未执行）

必须先由主负责人得到真实 accepted delivery 并通过主 consumer 的完整离线 check，然后按已有授权、当次 owner/driver 安全边界进行 SRAM 操作。本脚本不放宽这些门槛。

1. PC 与 RK 的 UTC 时钟先核对并记录；边界与 journal 时间需要同一可比较时间基准。不能把 clock skew 当正常通过。记录 driver before（例如当次原始 dmesg/journal、驱动枚举和 ownership 命令输出），保留原命令、stdout/stderr/exit/time。
2. PC 在真正 consumer execute 前运行 `python collect_program_session_v2.py --start --output <new/session.json> --delivery <actual-delivery.json> --collector <name>`。然后主负责人独立执行已经授权的 consumer command，并完整保留输出和退出码。命令返回后立即 `python collect_program_session_v2.py --complete --output <same/session.json> --delivery <same-delivery.json> --receipt <actual-run/receipt.json> --exit-code <实际退出码> --collector <name>`。collector 自身只记录本地时间与文件hash，绝不调用 consumer；不能事后替旧 run 重建成功时间。
3. 后续授权启动实际 viewer 时，将 stderr/stdout接入 systemd journal（优先原 viewer systemd unit 的 StandardOutput=journal/StandardError=journal），确认实际 viewer PID，并检查导出记录的 `_PID/_EXE` 确属该 viewer。使用 systemd-cat 等 wrapper 时不能假定 journal 的身份归属，若字段仍指向 wrapper 则不合格。不能给旧 text log 后补假 `_PID` 字段。若现有启动不能保留 journal 身份字段，先保留 pending；不要把日志改造成伪实采。
4. 将 `collect_viewer_proc_v2.py` 提供给 RK 后，板端运行 `python3 collect_viewer_proc_v2.py --pid <实际viewer PID> --host <实际截图host> --model <实际loaded-model-absolute-path> --model <第二实际模型路径> --output <identity_before.json>`。这是只读 /proc/文件的 collector，不触碰 /dev 或启动/停止进程。model 参数须与 viewer 实际加载的模型一致。保留 current readonly model identity 用于预期绑定。
5. PC 两次执行既有 `project/tools/capture_rk3568_screen.py --output <new/shot1.png>`、`--output <new/shot2.png>`，间隔足够使真实画面和采集日志有进展。当前 capture 日志约每5秒一次，先等首个采集统计再截图，并在第二图之后等下一条统计再取 identity_after，保证主四路日志跨越两图。保留每次生成的原 PNG/XWD/JSON，不改 metadata。RK 导出 `journalctl --no-pager -o json _PID=<PID> _BOOT_ID=<去掉连字符的boot-id> --since '<viewer-start UTC>' --until '<identity-after UTC>'` 的完整原始 stdout；不能只挑成功行。核对进程与模型实际日志。
6. 获得四路 diagnostic source 当次 raw 和前后 driver 日志。如果 main/source 并没有可核验诊断采集入口，由主负责人确认实际支持的现有只读接口；不要新发 DMA、写寄存器或猜造六路统计。driving demo 的 C5/C6 如无采集进展，按已有设备授权另作 supplemental capture session、另采前后 /proc和 journal，不把四路画面判失败，也不把两路缺证判成功。
7. reviewer 实际打开两张图片，确认正常画面，并阅读 runtime/driver/diagnostic原始材料。normal_frame_integrity 须引用 runtime 日志、具体帧观察及限制说明；**图片、positive fps 或无 timeout 都不能独自证明 DMA full completion**。无需给原版本新增 AXI 硬证书，脚本结果始终标明 automatic_dma_full_completion_proof=false。same_board_identity review 引用 baseline 与两个 current身份；program_delivery_check review引用当次delivery/receipt/cfg且确认主consumer完整check。
8. 按模板填实采条目与原文引用，所有 pending 消除后 reviewer 才可 accepted=true；执行 `python new_validate_board.py --evidence <actual-v2.json>`。返回 reviewed_evidence_complete 仅意味着严格离线一致性和人工评审附件完整，不是自动视觉识别或采集真实性密码学认证。

## 本轮本地验证

`python test_board_validation_v2.py`：8项测试通过，包含错 executable/hash/args/model、viewer/receipt/log timestamp、缺第二张、重复截图、false frame progress、pending/假引用、v1/fill-less v2 CLI拒绝。真实 baseline 三文件能重读转换，**作为 post-program 图必须拒绝**；真实历史 cfg parser 与 receipt stages 一致，但不产生新 delivery acceptance。24/32像素存储采用小语义样本验证，不生成伪真实 positive manifest。测试入口同时 py_compile 四个新增/修改 Python 文件。`python local_compatibility_check.py` 已运行通过，接入严格 v2 反例和 template/v1拒绝，真实RTR/历史cfg解析兼容性检查保留。

限制：未运行任何上板采集脚本、未SSH、未device、未program；目前没有两张当次post-program图片、当次viewer journal或diagnostic raw，最终板端验收仍未完成。机器只核验可解析的事实和原文绑定，物理板身份/画面/帧完整性/诊断来源的实际判断由明确的 reviewer 承担。
