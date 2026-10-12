# 当前板端复位接口纠正

2026-10-06 同 boot `dd39b8d1-cf2d-404e-914d-45eb87278794` 的只读设备树证据确认：gpiochip4 的 GPIO144 对应 bank4 pin16，provider phandle为0x8e。其实际消费者是 `/dsi@fe070000/panel@0/reset-gpios=<0x8e 16 1>`，compatible为simple-panel-dsi、status为okay。这与debug GPIO中的kernel consumer `reset`、ACTIVE LOW一致。它是当前显示面板复位接口，不能作为当前PCIe PERST使用。

原始证据为 `gpio144_consumer_readonly01.stdout.json`，命令、采集时间、退出码及输出SHA256见同名前缀的receipt.json。未写GPIO、未打开DMA设备、未执行复位。

当前domain2 PCIe节点是 `/pcie@fe280000`，完整属性没有reset-gpios；pipe复位引用CRU phandle0x24、索引0xc1。vpcie3v3-supply phandle0x140解析为regulator-fixed节点 `/gpio-regulator`，名称vcc3v3_pcie，其实际属性没有gpio/gpios开关。对应证据为 `pcie_dt_properties_readonly01.stdout.json` 和 `reset_dt_providers_readonly01.stdout.json`。这些事实不能推出外部PERST不存在，也不能证明普通reboot会清除FPGA全部事务。

`reset_interface_readonly01.stdout.json` 已确认当前endpoint sysfs reset_method为bus，FLReset不支持。已有审查指出此接口会保存/恢复PCI配置，且单独PCIe reset不能替代完整FPGA SRAM会话重建。当前尚无执行复位或DMA空闲证明。

本文纠正旧协议GPIO144操作应用于当前板端的假设。后续不得运行该旧GPIO脚本；完整会话重建仍须按真实BME禁止、主机boot边界、完整SRAM重载与新镜像guard启动顺序留证。构建签核要求和consumer保持原样。
