# main OV5640→PCIe

本目录承载 `codex/main-ov5640-pcie` 的独立产品实现。当前已完成从 M1-A 采集、M2-A
灰度处理到 M3-B 双槽/canonical DDR3/vendor MWR TX 应用边界，不依赖 `parallel_driver`。

## 当前文件

- `rtl/ov5640_dvp_rgb565_capture.sv`：`cam_pclk` 域字节拼接、像素坐标和帧/行事件。
- `rtl/rgb565_grayscale.sv`：RGB565 灰度化，固定一拍处理延迟。
- `rtl/ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的板级无关连接。
- `rtl/rgb565_word_packer.sv`：RGB565 像素到 128-bit 数据字的顺序打包。
- `rtl/ov5640_dvp_rgb565_word_pipeline.sv`：采集、灰度处理和 128-bit 打包连接。
- `tb/tb_ov5640_dvp_rgb565_capture.sv`：采集模块两行三像素场景与半字节负向场景。
- `tb/tb_ov5640_dvp_rgb565_pipeline.sv`：采集到灰度处理的像素、边界和错误自检。
- `tb/tb_rgb565_word_packer.sv`：完整字、部分行尾字和控制事件自检。
- `tb/tb_ov5640_dvp_rgb565_word_pipeline.sv`：DVP 到 128-bit 图像字集成自检。
- `docs/MAIN_OV5640_PCIE_CAPTURE_CONTRACT.md`：模块接口和验证合同。
- `docs/MAIN_OV5640_PCIE_PROCESS_CONTRACT.md`：图像处理算法和延迟合同。
- `docs/MAIN_OV5640_PCIE_WORD_PACKER_CONTRACT.md`：128-bit 内部数据布局合同。
- `docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`：DDR3/PCIe 适配层职责、转换边界和关闭条件。
- `docs/MAIN_OV5640_PCIE_BOARD_INPUT_CHECKLIST.md`：真实板级闭环所需的一手资料和验收输入。
- `rtl/rgb565_word_to_axis4_adapter.sv`：M3-B 板级无关 128-bit 到 4-byte staging beat 适配。
- `tb/tb_rgb565_word_to_axis4_adapter.sv`：M3-B 字节顺序、keep、事件和背压自检。
- `rtl/rgb565_axis4_frame_accounting.sv`：M3-B 帧有效字节/beat/错误统计描述符。
- `tb/tb_rgb565_axis4_frame_accounting.sv`：帧统计描述符自检。
- `rtl/rgb565_axis4_frame_commit.sv`：规范化 DDR3 记录到帧提交/作废描述符。
- `tb/tb_rgb565_axis4_frame_commit.sv`：正常提交、槽号一致性、abort 作废、描述符背压和运行中复位自检。
- `rtl/rgb565_axis4_frame_slot_table.sv`：两个帧槽的写分配、committed FIFO、带槽 drop/done 回收控制面。
- `tb/tb_rgb565_axis4_frame_slot_table.sv`：双槽占用、顺序排队、单 reader、并发完成、容量越界和复位自检。
- `rtl/rgb565_axis4_frame_read_scheduler.sv`：从已提交帧首 token/记录数生成单 outstanding DDR3 记录读命令。
- `tb/tb_rgb565_axis4_frame_read_scheduler.sv`：不可提交隔离、命令背压、零延迟响应、帧尾不一致恢复、地址推进和复位自检。
- `rtl/rgb565_axis4_frame_readout_gate.sv`：只为已提交帧打开 DDR3 记录读出窗口。
- `tb/tb_rgb565_axis4_frame_readout_gate.sv`：已提交帧透传、响应资格门控、完成关闭、错误帧隔离和运行中复位自检。
- `rtl/rgb565_axis4_committed_pcie_mwr_path.sv`：帧提交、统一读响应调度、fault 恢复和规范化 PCIe MWR 组合切片。
- `tb/tb_rgb565_axis4_committed_pcie_mwr_path.sv`：错误帧隔离、正常帧恢复及等待 ACK 请求复位清除的联合自检。
- `rtl/ov5640_dvp_rgb565_ddr3_pcie_pipeline.sv`：OV5640 DVP、按槽 DDR 写入、帧提交/读回和 PCIe MWR 的 vendor-independent 顶层。
- `rtl/ov5640_dvp_rgb565_dma_staging_pipeline.sv`：OV5640 到 staging/帧描述符联合 wrapper。
- `tb/tb_ov5640_dvp_rgb565_dma_staging_pipeline.sv`：联合数据路径自检。
- `rtl/rgb565_axis4_mwr_descriptor.sv`：板级无关的规范化 PCIe Memory Write 请求描述符。
- `tb/tb_rgb565_axis4_mwr_descriptor.sv`：请求地址递增、keep、last 和 4 KB 边界自检。
- `rtl/rgb565_axis4_pcie_mwr_bridge.sv`：统一锁存数据、地址、keep 和帧事件的临时 PCIe 请求桥。
- `tb/tb_rgb565_axis4_pcie_mwr_bridge.sv`：请求全字段保持和 ack 释放自检。
- `rtl/rgb565_axis4_pcie_mwr_path.sv`：staging→MWR descriptor→请求桥的组合路径。
- `tb/tb_rgb565_axis4_pcie_mwr_path.sv`：请求地址、4 KB 边界及等待 ack 时预取下一记录的字段保持自检。
- `rtl/rgb565_axis4_ddr3_write_descriptor.sv`：按帧接受 slot/base/capacity 分配并生成槽内规范化 DDR3 写记录。
- `tb/tb_rgb565_axis4_ddr3_write_descriptor.sv`：分配前背压、槽基装载、地址步进、容量夹断、多条越界记录和复位自检。
- `rtl/rgb565_pg2l50h_ddr3_write_adapter.sv`：规范化记录到 PG2L50H canonical AW/W 用户写口的单 outstanding 适配。
- `rtl/rgb565_pg2l50h_ddr3_read_adapter.sv`：PG2L50H canonical AR/R 用户读口到带背压规范化记录的单 outstanding 适配。
- `rtl/ov5640_dvp_rgb565_pg2l50h_pcie_pipeline.sv`：把 OV5640 双槽主链与 canonical DDR3 读写口、MWR32 请求边界串接的可综合应用层。
- `tb/tb_ov5640_pg2l50h_ddr3_pcie_loopback.sv`：canonical DDR3 AW/W、AR/R 模型到未修改 vendor MWR TX 的闭环自检。
- `rtl/rgb565_axis4_async_fifo.sv`：携带 `data/keep/last/user` 的板级无关双时钟 staging FIFO。
- `tb/tb_rgb565_axis4_async_fifo.sv`：异步时钟、满/空、顺序和握手自检。
- `rtl/rgb565_axis4_cdc_bridge.sv`：异步 FIFO 的 staging 上游/下游 CDC 封装边界。
- `tb/tb_rgb565_axis4_cdc_bridge.sv`：双时钟数据顺序与首/末事件完整性自检。
- `rtl/rgb565_word_skid_buffer.sv`：两槽短突发缓冲及 overflow 整帧中止/下一帧恢复。
- `tb/tb_rgb565_word_skid_buffer.sv`：顺序、中止记录、余帧丢弃、恢复和 sticky overflow 自检。
- `rtl/ov5640_dvp_rgb565_cdc_staging_pipeline.sv`：OV5640 DVP 到双时钟 staging 输出，带源端压力报告。
- `tb/tb_ov5640_dvp_rgb565_cdc_staging_pipeline.sv`：小帧正常路径与长帧压力、事件和 `source_overflow` 自检。
- `tb/tb_ov5640_ddr3_pcie_loopback.sv`：正常帧、overflow 中止和下一帧恢复经 DDR3 模型回送 PCIe 的行为级自检。
- `scripts/run_m3b_ov5640_ddr3_pcie_loopback.ps1`：上述往返自检的可重复 Questa 入口。
- `tb/tb_ov5640_ddr3_committed_pcie_loopback.sv`：将帧提交、读命令调度、错误帧作废和 PCIe MWR 接入同一行为闭环。
- `scripts/run_m3b_ov5640_ddr3_committed_pcie_loopback.ps1`：上述已提交帧行为闭环的可重复 Questa 入口。
- `tb/tb_rgb565_pg2l50h_mwr32_tx_integration.sv`：项目 bridge 到原始 PG2L50H MWR TX 控制器的单 DWORD动态集成自检。
- `scripts/run_m3b_pg2l50h_mwr32_tx_integration.ps1`：上述 canonical vendor TX 自检的可重复 Questa 入口。
- `rtl/rgb565_pg2l50h_pcie_tx_request_arbiter.sv`：完整 native TX 请求 bundle 与 camera MWR32 的同域轮转仲裁边界。
- `tb/tb_rgb565_pg2l50h_pcie_tx_request_arbiter.sv`：四类 native 请求透明通过、owner 保持、ACK 隔离、轮转与模式保持自检。
- `tb/tb_rgb565_pg2l50h_pcie_tx_arbiter_integration.sv`：native RAM-data 和 camera user-defined MWR32 共享未修改 vendor TX 的动态自检。
- `rtl/rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv`：DDR `core_clk` 到 PCIe `pclk_div2` 的单 outstanding MWR32 toggle/bundled-data mailbox。
- `tb/tb_rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv`：双速率、连续事务、保持型 ACK、idle/在途复位与 fault 合同自检。
- `rtl/rgb565_pg2l50h_pcie_tx_cdc_arbiter.sv`：mailbox 与完整 native/camera TX 请求仲裁的可综合连接层。
- `tb/tb_rgb565_pg2l50h_pcie_tx_cdc_arbiter_integration.sv`：异步 camera 与 native 请求经未修改 MWR TX 输出两组 TLP 的动态自检。
- staging、帧统计和规范化请求描述符已完成同域行为验证；DDR3 写记录层已完成边界回归，
  staging 异步 FIFO 已完成双时钟行为验证；行为级 DDR3 模型已将正常帧、overflow
  中止记录和恢复帧送入 PCIe MWR 请求路径。提交描述符现在携带首个 opaque token，调度器
  按记录数发出有界读命令，并统一处理零延迟响应、提前/缺失帧尾和零记录 fault。双槽表现已
  接入 writer、frame commit、scheduler 和 committed wrapper；完整行为回归覆盖两个正常帧排队、
  带槽完成、错误帧 drop 和槽复用。PG2L50H 应用层现已接到 canonical DDR3 AW/W 与 AR/R 端口；
  每条记录的 keep/last/frame-end/error 写入第 5 byte，读适配器用必要的单条弹性寄存器恢复 sideband。
  独立 PG2L50H MWR32 TX 专项已验证 full-DWORD 请求的 ACK、header、地址和数据输出；项目自有
  mailbox 与仲裁层已把 camera 请求从 DDR `core_clk` 安全送入 PCIe `pclk_div2`，并与完整 native
  request bundle 共享未修改 MWR TX。完整 DMA 顶层实例化、partial keep、链路和主机内存仍未关闭。

## 运行

```powershell
.\scripts\run_m1a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m2a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3a.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_accounting.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_frame_commit.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_frame_slot_table.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_frame_read_scheduler.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_frame_readout_gate.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_committed_pcie_mwr_path.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_integration.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_mwr_descriptor.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pcie_mwr_bridge.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pcie_mwr_path.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_mwr32_tx_integration.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_pcie_tx_request_arbiter.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_pcie_tx_arbiter_integration.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_pcie_mwr32_async_mailbox.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_pcie_tx_cdc_arbiter_integration.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ddr3_write_descriptor.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_ddr3_write_adapter.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_ddr3_write_path.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_pg2l50h_ddr3_read_adapter.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ov5640_pg2l50h_ddr3_pcie_loopback.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_async_fifo.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_cdc_bridge.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_word_skid_buffer.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ov5640_cdc_staging.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ov5640_ddr3_pcie_loopback.ps1 -SimulatorExecPath '<questa-bin-dir>'
.\scripts\run_m3b_ov5640_ddr3_committed_pcie_loopback.ps1 -SimulatorExecPath '<questa-bin-dir>'
```

运行态只写入 `main_ov5640_pcie/build/`。`vsim.exe`、`vlog.exe` 和许可证配置由本机
环境提供，不写入仓库。两槽 word 缓冲只能吸收短突发；`source_overflow=1` 表示
当前帧在进入帧缓存前发生了无法接收的 word。该帧会以空载错误帧尾结束，余帧被
丢弃，并只从后续 `frame_start` 恢复；这保证损坏帧可识别，不代表持续背压无丢帧。当前切片不生成
PDS/IP/位流，也不证明 SCCB、板级电气时序、真实 DDR3 或完整 PCIe 系统集成。M3-A 的
128-bit 布局不等同于厂商 PCIe AXIS `tkeep` 或主机内存字节序，M3-B 适配层必须按
独立合同冻结转换规则后再实现。往返 TB 中的 DDR3 地址是模型槽位，PCIe 地址使用
`0x0ffc` 起始并按 `keep` 有效字节推进；这只证明行为级字段贯通，不证明真实地址单位、
DDR3 初始化、完整 PCIe DMA 仲裁、链路或主机内存写入。新增 canonical 应用层回归证明记录跨过
AW/W 和无 RREADY 的 AR/R 边界并恢复元数据；它仍使用明文用户口模型，不等价于加密 DDR3 core
仿真或实板存储。canonical 回归现已通过单 outstanding mailbox 跨过 DDR/PCIe 异步时钟并进入
未修改 MWR TX；它仍不等价于完整 TX top、PCIe 链路、主机完成或 placed-design CDC/STA 签核。
