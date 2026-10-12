# reboot → qualifiedV7 SRAM → PCIe trial07 实际结果

已按新授权执行一次 `sudo -n reboot`，实际 boot 从 `c1500212-6832-4215-a2b2-76b60c8c3858` 变为 `925a0f3d-b23b-46e5-b02b-b387a380402e`。

PDS 忙时没有持 global mutex。工具空闲后取得 `Global\ov56401_PDS_single_instance`，持锁期间再次确认工具空闲，并调用原 `timing_correction_05/program_board.py`；该入口真实执行 `verify_delivery.py` 后才进入 vendor SRAM 编程。

SRAM 比特流 SHA256：`dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`。原始 vendor receipt：`C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\run_20261007_141457_1864fb5d\receipt.json`。全部 vendor stages 为 true（包含 program_success、final_scan_success、final_target_single、device_done），原始 cfg 日志经 actual06 的 v7_program/vendor_parser 重新解析和 hash 绑定。

直接编程后立即及约 10 秒后的自然枚举结果见 `post_sram_natural_immediate.stdout.txt` / `post_sram_natural_10s.stdout.txt`。最终 PCI 设备：`[]`；驱动节点：`[]`。

Rescan 独立结果：`{"executed": false, "reason": "No actual PCI root/rootport: host probe failed, rescan cannot revive a missing host"}`。没有实际 root/rootport 时，没有写全局 rescan，没有假 bind/load 模块。

LTSSM 为本 boot 的内核启动日志，不能冒称编程后的实时寄存器采样。以下保留编程后快照中的实际日志：

```
[    3.101971] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.123024] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.144056] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.165090] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.186124] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.207153] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.228183] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.249216] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.270249] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    3.291279] rk-pcie 3c0800000.pcie: PCIe Linking... LTSSM is 0x0
[    5.200292] rk-pcie 3c0800000.pcie: PCIe Link Fail, LTSSM is 0x0, hw_retries=0
[    5.200314] rk-pcie 3c0800000.pcie: failed to initialize host
```

admission 保持 `0644`。无 Flash、GPIO144、held SBR、第二次 reboot、driver unload、viewer 启动或 admission release；未更改软件 buildhash，未交付新 candidate bit，未完成 goal。第一次只读 preflight 因过宽 viewer 名称判断退出，未执行 reboot；保留 initial_preflight.failure.json 和 stdout，后修正为实际设备 holder/映射与受管 producer 判断，不向 HDMI 进程发信号。

每次 SSH/local command 的 UTC、rc、command/stdout/stderr SHA256 见同名 receipt；完整 evidence hash 索引见 audit.json。
