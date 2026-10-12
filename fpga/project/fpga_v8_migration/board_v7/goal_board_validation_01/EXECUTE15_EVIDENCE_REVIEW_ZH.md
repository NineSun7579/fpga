# execute15 交付证据审阅

目标仍为：生成可用的新 bit、实际 SRAM 烧录，并获取 RK3568 真实相机截图验证功能。本文仅记录对现有交付代码的审阅，不代表构建、烧录或板级验收通过。

## 已核对的检查范围

- `check_functional_bit09.py` 重新读取原生 global10 与 crossing 报告，核对 Slow/Fast 的 Setup、Hold、Recovery、Removal、Minimum Pulse Width 十组非负裕量，以及零失败端点、零 TNS 和非空端点。实际 crossing 数量来自候选 physical inventory，不固定沿用旧数量。
- 检查器绑定新 `.sbit` 的大小和 SHA256、实际 route、741 个源输入、186 个登记源、原生 CDB、官方 genbit 日志，以及 map13、route14、hold15 恢复输入。hold15 的 PnR 回执必须成功且日志哈希一致。
- `functional_delivery_execute15/runner.py` 要求 manifest 和 hold15 binding 存在后才进入完整交付检查；复用 corrected11 的重启、SRAM、PCIe 恢复和两种 viewer 模式。最终结果刻意保留 `goal_complete=False` 与 `functional_pass=False`，等待实际证据审阅。
- viewer 使用真实相机入口；六路模式为 `--prefer-hdmifull off`，driving 模式绑定 `trafficlight-16cls,wb_v4_combo`。每个模式核对 ELF、argv 和 owned process identity，收集完整日志及真实退出状态。
- `capture_camera_session09.py` 拒绝 `--video`，按 viewer PID 查找唯一可见 X11 窗口；每张截图前后核对 boot、ELF、argv、process starttime 和窗口身份。两张 XWD/PNG 相隔 10 秒，元数据保存 bit 与 SRAM 回执文件哈希，同时保留 dmesg。

## 收到实际产物后的必要审阅

1. 重新核对 `checked_bit_handoff.json` 与 `sram_program/receipt.json` 的 bit SHA256、vendor 成功阶段和 DONE；检查 `boot_binding.json` 确实记录重启。
2. 两模式每张截图元数据中的 boot 必须等于 SRAM 回执和最终板态的 boot；截图时间必须晚于该次成功烧录结束时间，输入回执和 bit 哈希必须逐一相等。采集器仅保存输入文件绑定，不能单靠 collection 状态推断这些跨文件关系已通过。
3. 打开四张真实 PNG，核对六路实际画面和 driving 的 C5/C6 与模型输出；审阅帧/tag 进展、推理完成/失败、两份完整日志及 dmesg。PCIe 枚举和 viewer 启动不等于相机正常。
4. motion 仍需实际画面或运行记录支持。若静态场景与现有日志无法判断，应继续针对性观测；不能以源保留或构建成功代替功能证据。

不得将此前 V7 SRAM 回执、桌面截图、route01 的完整 crossing 覆盖或本轮路由局部 hold 修复，转移为新候选的最终通过状态。
