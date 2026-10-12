实际恢复成功：本次只执行一次标准 platform host bind，返回码 0，恢复真实 PCI root 与 FPGA endpoint。功能/DMA/画面 PASS 仍为 false。

- 全程 boot_id：925a0f3d-b23b-46e5-b02b-b387a380402e，live Linux 6.1.99，board_host=192.168.10.203。
- 失败实例：3c0800000.pcie；真实 live host driver 为 rk-pcie。启动 5.200292 秒报 PCIe Link Fail, LTSSM 0x0，随后 failed to initialize host，fresh 时 driver 未绑定、PCI devices/buses 均为空。
- live DT：/pcie@fe280000，compatible rockchip,rk3568-pcie / snps,dw-pcie，domain 2，bus-range 20–2f，2 lanes。这里“PCIe2”应依据实际 domain/端口映射解释，不能凭名称操作其他控制器。此前 pcie_parent_bridge_readonly01.stdout.json 中真正 endpoint 路径也位于该实例下。其余 fe260000、fe270000 DT PCIe 节点 disabled。
- 操作前核验：精确 platform 实例及 DT reg/ranges/PHY；平台未提供 resource 文件（ENOENT 已保留），用 live DT reg、/proc/iomem 和 sysfs children 核验替代。无 PCIbus/endpoint；无 pango 节点、无 pango/xdma/devmem/目标控制器 owners；rk-pcie bind 存在。非显示设备，不动其他主控/PHY/供电驱动。
- 实际唯一 host 写入：将 3c0800000.pcie 写入 /sys/bus/platform/drivers/rk-pcie/bind，write/flush rc=0。bind_once.command.txt 保存完整 Python 等价命令；stdout/stderr 与 SHA-256 见对应 receipt。未 unbind、未 rescan、未 reset、未 reboot。
- bind 返回后的最早 sysfs 快照暂为空，随后同命令 lspci 已看到 root/EP；再次独立 enumeration 与 final 核验 sysfs 确认，不将早期异步快照视作失败或再 bind。
- 4040.691833 秒日志：PCIe Gen.2 x2 link up；4040.692152 秒建立 bus 0002:20；4040.724070 秒发现 [0755:0755]。root 0002:20:00.0，endpoint 0002:21:00.0，5.0 GT/s ×2。
- BAR0 f0200000–f0201fff (8 KiB)，BAR1 f0202000–f0202fff (4 KiB)，BAR2 f0203000–f0203fff (4 KiB)。只读 resource 元数据；本工具未打开 BAR resource 或 DMA 字符设备。
- 核验现存模块 /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko：SHA-256 0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861，build-id 1102cfd04acaeeea21ca4d03fe27ddbb32b7340a，vermagic 6.1.99 SMP mod_unload aarch64；与 trial07 留存验证一致。一次 insmod rc=0，正常 probe 完成，绑定 pango_pci_driver。
- endpoint MSI Enable+ Count=4/4，sysfs IRQ 128、129、130、131；这证明分配/启用，不证明中断实际数据流。/dev/pango_pci_driver mode 0600，major 511/minor 0；owners=[]，扫描错误=[]，module refcount 0。
- 模块正常 probe 会 pci_request_region/ioremap、设置 DMA mask 与 BME；均为已授权 insmod 的驱动初始化，本次没有发起 DMA。BME+ 不作为功能通过依据。最终 iomem 在 BAR1 下显示 <BAD> resource 名称，原始内容保留，不据此扩大为链路故障或功能 PASS。
- admission 维持 0644，SHA-256 72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703；未启动 FPGA viewer。现有屏幕 Xorg PID1372、视频 detview-hdmifull PID4128、ffmpeg PID4145 在前后均存在，未向其发送信号或修改显示配置。标准 bind/insmod 触发内核对已有 deferred backlight 的重试日志，未见本次显示重设证据。
- 工具仅调用 board_host SSH、Linux DT/sysfs/proc/lspci/dmesg/readelf/modinfo 和一次 bind/insmod，不调用 FPGA programmer/PDS，不修改构建输入、DT、内核、GPIO144、Flash；可与独立 FPGA 构建并行。

现场支持的原因是：早期主控初始化失败并留下 unbound 状态，之后 SRAM DONE 不会自动使这个 host 重新 probe；DONE 后标准 bind 已恢复链路与枚举。本次不归因为硬件损坏。完整旧失败日志和新成功日志均保留。

下一步已具备真实 endpoint 与驱动条件：交回主会话进行其授权范围内的受限 DMA/帧内容与实际画面验证；保持 admission hold，不能因为枚举、MSI 或 BME 成功直接解锁并报告功能 PASS。当前 endpoint 存在，不再重复 host bind/reset。

fresh、scope、bind_once、enumeration、insmod_once、final 各自都有完整 command / rc / stdout / stderr / hashes。dmesg_before.stdout.txt、dmesg_after.stdout.txt 保存独立原始日志；result.json 汇总现场结论，manifest.json 记录文件 SHA-256。
