# 实际驱动复查及交接

驱动的 DMA 采集本次已恢复，五路摄像头持续更新，C5 仍只有静态帧。不能称为六路全部正常。

原模块 `/root/ov5640/pango_pci_driver.ko` SHA-256 为 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`，与预先存在的 `pango_pci_driver_fixed_20260926.ko` 完全一致；与目录中更早的 baseline 模块不同。SHA-1 与既有修复文档记载一致，vermagic 为 `6.1.99 SMP mod_unload aarch64`。本次未改动、重编译驱动或烧写 FPGA。

检查开始时无采集程序占用设备。PCIe 链路为 5 GT/s x2，Memory、BusMaster、MSI 均启用，BAR 布局正常。已有内核日志包含 MSI 完成超时及后续 `g_dma_flag=1` 导致的 DMA 空闲超时。驱动源码显示此超时保留 DMA 所有权，避免在硬件传输未完成时覆盖描述符；本次没有修改该逻辑，也没有伪造中断。

本次在无占用状态下卸载原模块、移除 PCIe 端点、rescan、等待 2 秒，重新加载同一原模块并等待 1 秒后恢复采集。此前同类恢复曾失败，因此这里只记录本次有效，未证明失败的根本原因或重启后的永久修复。

原 detview 原文件 SHA-256 `3d315e77913fb651b884b817480284d1ad17ad5e794866f4db5c7c50db69cf0b`，以 `--model MVP_accuracy_round1 --fullscreen --no-tracking --duration 10` 实际运行，退出码 0。DMA IRQ0 从 0 增长至 14,336。C1/C2 约 45 fps，C3/C4 约 26 fps，C6 约 41 fps，六路 ioctl 错误计数均为 0。C5 初始一帧后为 0 fps。

之后环视程序实际采集 30 秒，C1/C2/C3/C4/C6 的累计新帧数分别为 857/857/757/737/844；C5 仅 1 帧，tag1071 不递增。DMA IRQ0 累计至 32,976。此数据可作为驱动证据，UI 与几何验收已因用户双目拓扑更正作废。旧配置认为六路朝向不同，不能据此宣称正确环视、鸟瞰或双目几何。旧日志和截图需标记 superseded。

交接时已恢复原 detview，PID 3086，参数 `--model MVP_accuracy_round1 --fullscreen --no-tracking`，为设备唯一占用者。IRQ0 累计至 185,199，采集仍持续更新；从恢复测试开始到交接的内核窗口有 78 行，新增 DMA 超时、采图错误、Oops、BUG 均为 0。C5 的静态状态在原程序与环视程序均出现，原因尚未定位，不能归因于 UI。

重要：旧环视程序在收到拓扑更正之前已被测试脚本安装；收到更正后已移至 `/userdata/surround360/evidence/driver_check/surround360_topology_superseded`，当前 `/userdata/surround360/surround360` 不存在，避免作为完成版启动。原 run_surround360.sh 仍在，父会话完成拓扑修正后需要重新安装候选程序。未改现有 calibration.json，备份位于同目录 `calibration_before_topology_correction.json`。自测参数 `--calibration-test` 只打开并截图面板，不执行保存或实际标定。

原始证据的最新本地副本在 `board/driver_check/`；最初副本在 `board/`。完整内核日志包含恢复前的历史失败，判断本次健康请使用 `kernel_verified_window.txt`。结构化结果为 `driver_health.json`。

板卡独占权交回父会话。后续必须使用修正后的前向 C1/C2、侧向 C3/C4、后向 C5/C6 拓扑重新测试和安装环视程序；后向应允许 C5 静态时使用持续更新的 C6。
