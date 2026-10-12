# 摄像头读预译码隔离候选与逐周期等价回归

结果：P1 RTL 候选已实现；ModelSim SE-64 10.6e 实际模块并排回归 PASS。6 组各 21,690 周期，共 130,140 周期，所有输出逐拍比较无差异。候选未运行 PDS，不能据此声称时序已闭合。

## 源码与 exact09 证据

- 原文件：`../source_diagnostics_route_02/inputs/source/ov5640/ov5640_reg.v`，13,127 bytes。
- 原 SHA256：`96af9a56e1c60ae688ac045296ba0b128bace1fc4d2a25e2e6793b12299ea140`。
- 候选：`rtl/ov5640_reg.v`，15,953 bytes，SHA256 `984d8bcbaa41cab792f48b3a3cfc910655508e23c173c68a9091c8a3491d1313`。
- actual exact09 `input_hashes.json` SHA256：`45e3b1d5ed79ac8b0782f64a9f12f1ad8a463306f4688a864269534e7470fe89`；其中 camera 文件哈希与原文件一致。
- 从 actual exact09 `all_reported_failing_paths.json` 提取 `ov5640_reg/raddr_reg[*] → ov5640_reg/rdata[*]`，128 条 slow setup 路径，WNS −4.412 ns。完整路径与来源哈希见 `evidence/exact09_camera_target_paths.json`。这不是全部 camera 负路径。

原文件是 legacy GBK/mixed 注释字节，严格 GBK 解码在 byte 8916 失败。`original/ov5640_reg.v` 保存精确 bytes；生成器不做全文件解码/转码，只替换两段 bytes。`evidence/byte_patch.json` 保存删除/新增段的 base64 与偏移，审计可精确重建候选。`evidence/candidate.patch` 是 UTF-8 可读 diff，坏编码注释用替代字符展示，应以 byte patch 为精确依据。

## 实现与参数分析

22 个读 case 项都是 `BASE_ADDR` 加常量或 localparam；`BASE_ADDR`、默认寄存器值和 `AXI_ADDR_WIDTH` 均为 elaboration 参数，没有运行时地址项。可在综合展开时求值；未硬编码当前默认 BASE、截取低地址位或引入 `casex/casez`。

候选在原 AR 捕获条件 `s_axi_arvalid & s_axi_arready` 下寄存 23 位选择：22 个地址和默认项。采用与原 case 完全同序的普通 `case(s_axi_araddr)` 产生单热码，因此匹配项碰撞时第一项胜出。没有采用独立并行比较直接构造多热码，避免多项命中时把数据 OR 混合。数据边沿用定宽数据 wire 的掩码 OR；定宽 wire 保持原赋值的扩展/截断语义。

有限、已知 BASE 下，22 个不同 offset 的数学地址在原 case 的比较宽度中互异；缩窄 AXI 地址宽度不会把原 case 常量提前截断成碰撞。TB 另用全 X BASE 制造原普通 case 的实际重复项碰撞，验证 first-case。候选保留 4-state 普通 case 语义；回归不是任意参数/任意 X 传播的形式证明。

`read_select` 与原 `raddr_reg` 一样，捕获本身不添加 reset 条件。`data_out_valid`、`r_state`、R/B valid、AXI ready 和所有写逻辑保留原 bytes。下一拍根据 select 取该拍 live debug/寄存器数据，没有提前锁存读值。32 位非法读保持 `ffffffff`；其他宽度仍全 1。高位和低四位 alias 继续完整比较，不映射成合法地址。

## 真实回归

原实际模块仅改名为 `ov5640_reg_reference`，候选实际模块仅改名为 `ov5640_reg_candidate`。TB 没有重写 reference 行为；两模块共享刺激，每拍在 NBA 完成后比较所有输出，包括 AXI、camera 配置、ACK 和 SCCB 控制。CSV 同时记录全部输出打包值，`audit_evidence.py` 独立逐行比较。

|组|参数场景|周期|读捕获|写握手|R背压周期|reset|读写同拍|
|---|---|---:|---:|---:|---:|---:|---:|
|0|默认32位|21690|1351|4987|4232|22|255|
|1|BASE 20000100|21690|1394|5054|4138|21|278|
|2|BASE ffffff80，回绕|21690|1406|5026|4148|22|242|
|3|64位，BASE 120000000|21690|1372|4921|4114|28|257|
|4|16位，BASE 0|21690|1399|5167|3994|29|279|
|5|X BASE，case 项碰撞|21690|1304|4972|4195|22|265|

定向覆盖所有 22 个合法读地址、每项低位 alias 1..15、翻转最高位 alias、write-only/非法地址、5/8 拍 R 背压、取数边沿 debug 变化、SCCB 完成与写命令事件、AR 同拍写、取数同拍写、AR/取数/持有响应三个时刻 reset。随机每组 20,000 周期，独立 seed，混合 VALID、READY、地址、WSTRB、数据、debug 和 reset。

额外语义断言检查：固定下一拍 RVALID、默认非法数据、当拍 fault 数据、first-case 碰撞、背压数据稳定、AR 边沿写后新值、取数边沿写时旧值以及 reset 压过读写。数字计数包括主要握手刺激，reset 定向序列不作为有效事务统计。

真实日志：`evidence/modelsim_cycle_miter.log`，编译 Errors 0 / Warnings 0，仿真 Errors 0，只有现有配置 `-novopt` 警告。初次使用中文 `-l` 路径触发 ModelSim 旧 Tcl 启动异常，改用 ASCII 日志路径后完成真实仿真；中文标题与审计日志见 `evidence/周期等价审计.log`。

复现（在候选目录）：

```powershell
python build_candidate.py
Set-Location sim
& 'C:/modeltech64_10.6e/win64/vsim.exe' -c -do run.do -l '../evidence/modelsim_cycle_miter.log'
Set-Location ..
python audit_evidence.py
```

## 剩余工作与隔离边界

本次只写新候选目录，没有修改 route02、生产、IP、frozen 或约束；没有运行 PDS、remote、program。时序 bugfix 不做 initiative capture。源哈希在仿真后复核未变。

物理验证仍需由后续独立流程完成：综合确认 23 位选择寄存器和数据 mux 实际映射；检查新 AR→select 路径、select→rdata 路径、面积/扇出、所有同域 setup/hold 和既有 reset/CDC 门槛。译码前移只改变组合逻辑所在边沿，不能保证 WNS 收敛。不要把当前回归 PASS 当成 −4.412 ns 已消除或 diagbit 可上板的依据。

交付入口：`rtl/ov5640_reg.v`、`evidence/input_hashes.json`、`evidence/byte_patch.json`、`evidence/candidate.patch`、`evidence/verification_summary.json`、`evidence/artifact_hashes.json`，以及 6 份 `sim/trace_*.csv`。
