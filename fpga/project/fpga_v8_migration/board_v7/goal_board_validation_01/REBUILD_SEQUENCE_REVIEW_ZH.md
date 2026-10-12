# 旧 session 失效与 rebuild 时序独立审查（只读）

本次唯一新增文件为本报告。未访问远端、未打开设备、未读写 BAR、未写 sysfs/config/GPIO、未提交 DMA、未重启、未执行 PDS/JTAG；只读取本地 retained 文件及公开源码。Hindsight 不可达，结论不依赖记忆。本文补充并替代 `DMA_IDLE_INTERFACE_REVIEW_ZH.md` 中关于当前 GPIO144 可用于 PERST 的执行假设，不改原报告、consumer、脚本或验收字段。当前结论：**有硬核 BME 发送禁止依据、有 Linux SBR 接口依据，但跨 boot 连续禁止旧 endpoint DMA 的实际时序尚未闭合；rebuild 未获硬件执行认证。**

## 1. 当前真实证据及身份边界

主会话提供的三个 stdout 在本地逐字节计算 SHA256，与各自 receipt 相符；不是 fixture。本报告没有重复 identity 采集。

| 保存证据 | receipt UTC | stdout SHA256 |
|---|---|---|
| `reset_interface_readonly01.stdout.json` | 2026-10-06T23:29:30.190493+00:00 | `97f20c67156ec50bf946ec7d4b02b3c1491bdcd55ed18e2a0f4bf16f83c587de` |
| `pcie_device_tree_readonly01.stdout.json` | 2026-10-06T23:30:03.370902+00:00 | `554305e999d9cdadcb3b36d07b9683052e4c4c0c35f4e4de6455713c1526db0e` |
| `pcie_dt_properties_readonly01.stdout.json` | 2026-10-06T23:30:17.150555+00:00 | `583a28bf9e313a1fce7776ec5ea72123d4301d7a2c8a725a375cfd666ba7a5ff` |

同次 boot 为 `dd39b8d1-cf2d-404e-914d-45eb87278794`，运行 kernel `6.1.99 #1 SMP Fri Mar 21 08:36:35 UTC 2025`。0755:0755 位于 `0002:21:00.0`，绑定 pango 驱动；loaded note 当前确认 build-id `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`。`reset_exists=true`、`reset_method="bus\n"`；FLReset-、TransPend-、BusMaster+、Gen2 x2。空 fuser stdout/返回1没有建立 hardware idle；本次 receipt 明确 `dma_idle_proven=false`。

完整 live node `/pcie@fe280000` 为 `rockchip,rk3568-pcie` + `snps,dw-pcie`，status okay，domain2，x2，bus-range 0x20..0x2f。**完整属性中没有 `reset-gpios`。** `resets=<0x24 0xc1>`、`reset-names="pipe"` 是 reset-controller 资源，不是 GPIO144/PERST 的对应证明；provider 尚须精确解析。`vpcie3v3-supply=<0x140>` 也不能单凭名称证明 FPGA rail 在 reboot 会掉电。

GPIO144 的三个 sysfs 属性不存在，debug 为 kernel consumer `reset`、ACTIVE LOW、out lo。consumer 名字不是 owner 设备路径；低电平/active-low 也不足以将它认作当前 PCIe PERST。**不采用旧 echo GPIO144 脚本，不 export、不抢占 kernel GPIO。** 后续只读解析可由主会话完成：定位 GPIO bank4 pin16 的真实 DT consumer（同时查 gpio/gpios/reset-gpios 等引用）；解析 phandle0x140 的 regulator 节点、GPIO及 always-on/boot-on/共享消费者；解析0x24 reset provider及0xc1定义；保留完整 node 和 receipts。需进一步区分 DT consumer 与运行驱动通过非 DT lookup 获得 GPIO 的可能性。

本地 project 文件名搜索及 retained migration/V7 inputs 检索未找到 `pci.c`、`pci-sysfs.c`、`pcie-dw-rockchip.c`、`pcie-rockchip-host.c` 或 `.dts/.dtsi` 内核源。板端保存证据显示 `/lib/modules/6.1.99/build` 缺失；`/usr/src/linux-headers-6.1-rockchip` 有 release headers，却没有被查找的 controller 源文件。因此下面 Linux 调用链是**公开参考源码**，不能宣布为当前下游 kernel 的精确实现。uname/build-id 不替代下游 source revision、config、补丁和 bootloader 时序。

## 2. Linux v6.1：sysfs bus reset 是什么

参考 [pci-sysfs.c](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/pci-sysfs.c#L1333) `1333–1353`：endpoint `reset` 写1调用 `pci_reset_function(pdev)`，不是直接调用 `pci_reset_bus()`。

参考 [pci.c](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/pci.c#L5134)：

1. `5450–5465`：lock → `pci_dev_save_and_disable` → 按方法复位 → `pci_dev_restore` → unlock。
2. `5220–5228`：方法名 `bus` 对应 `pci_reset_bus_function`；`5134–5142` 先试 hotplug slot 的 function reset，返回 ENOTTY 才走 `pci_parent_bus_reset`。所以 `bus` 字样本身不能排除 slot 实现；需真实父桥、slot 和下游 override 证据。
3. `5092–5108`：parent reset 拒绝 root bus、带 subordinate 的设备、缺 parent bridge、NO_BUS_RESET；还要求此 bus 上没有另一个设备。probe 成功只是支持检查，不是执行记录。当前 reset_method 能说明内核登记了方法，不能证明曾发出 SBR。
4. `5045–5089`：generic parent 路径调用 `pci_bridge_secondary_bus_reset(dev->bus->self)`，经 `pcibios_reset_secondary_bus` weak hook；默认读父桥 Bridge Control，置 `PCI_BRIDGE_CTL_BUS_RESET`，等待2ms，再清位、等待1s，然后配置可访问性等待。PCIe 对应链路 hot reset；源码没有 GPIO调用或 PERST 线操作。下游 hook/控制器映射需核验。
5. `5882–5913`：独立 API `pci_reset_bus(pdev)` 则优先 slot、否则 bus tree lock/save-disable/SBR/restore，作用域可能覆盖整棵 subordinate 树；不能拿此 API 描述直接等同 endpoint sysfs 路径。

**SBR/hot reset 与外部 PERST/fundamental reset 是不同边界。** 上述2ms/1s是协议及重新初始化等待，不是 AXI/R/B、FIFO或 host posted-write drain 证明。也不能把 Linux 注释“power-on state / clears all state”直接解释为 FPGA 用户 fabric、DDR、跨域 FIFO都已经复位。

### 配置恢复对 BME 的关键影响

`pci.c:5172–5217` 先 `pci_save_state`，再将 Command 写为 INTX_DISABLE（同时清 BME、MEM、IO）；结束时 `pci_restore_state`，并可能调用驱动 reset_done。**如果入口是当前观察到的 BME+，正常 sysfs reset 会恢复原配置中的 BME+。** 即使 reset 中暂时禁止 DMA，也没有建立直到 reboot/SRAM 重载完成的持续隔离。

因此未来初始顺序必须先停止新提交及可自动启动的驱动路径，明确清 BME并只读确认，然后做 bus reset，再确认 reset 后仍为 BME-；不能先在 BME+状态 reset，再以最后一次清 BME读回追认中间窗口安全。驱动 reset_prepare/reset_done/probe 的使能行为须纳入审查；禁止并发提交/重新使能的持续性不能仅靠一次读回。

## 3. Pango 硬核 BME 与 frozen V7 appcore/AXI 边界

安装版官方 `C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ips2l_pcie_gen2/ips2l_pcie_gen2_eval/ips2l_pcie_gen2/UG042004_Logos2_PCIe_IP.pdf`（83页，SHA256 `9deba94b50770cd6cf380421f0cb04bffb3f229d37e5cf6d338bdacce74c7d33`）：

- 第54页表2-23，Command offset004h bit2 Bus Master Enable，reset值0；**1可以发送MEM/IO类请求，0不可以发送MEM/IO类请求。** 这是本型号硬核阻止新的 Memory Read/Write 请求的直接依据，不因用户逻辑没连接状态输出而消失。不能进一步推成所有 Message/MSI、Completion也均由同一位禁止；表述只覆盖该表列出的请求类别。
- 第36页表2-20 的 `cfg_bus_master_en` 是配置 Command BME 位的状态输出；第35页的 `core_rst_n` 是硬核提供给用户逻辑的 pclk_div2域低有效复位。第35页 `power_up_rst_n`、`perst_n` 均来自插槽PERST#；第36页 LTSSM 包含 HOT_RESET_ENTRY/HOT_RESET。
- 手册检索未找到 hot reset 必然拉低 `core_rst_n` 的完整时序承诺，也没找到 BME=0会清用户 AXI state/取消已发 TLP/清 host posted队列的承诺。**禁止发新请求与取消旧事务必须分别论证。**

冻结目录简写 `V=project/fpga_v8_migration/whole_candidate_v7_route_01`；依据 retained frozen 输入，而非活动 source 副本：

| 具体文件及行号 | 可核验路径/结论 |
|---|---|
| `V/rtl/fpga_v8_pango_pcie_top_h2f_rfg01.v:226–243,559–567,71` | 外部 perst→同步→硬核 power_up_rst_n/perst_n；硬核 core_rst_n→DMA controller reset、fifo_pcie_rst=`~core_rst_n`。连接成立，不证明收到 SBR 时该硬核输出一定产生复位脉冲。 |
| 同文件 `:360–362,640,658–659` | controller rst_n接core_rst_n；BME、radm_idle及queue状态输出悬空，没有 host可读全域idle。 |
| `V/inputs/ipcore/pcie_test/pcie_test.v:321–324,525–530` | app_init_rst恒0；training_rst_n只有内部wire，未导出给应用控制。 |
| 同目录 `rtl/ips2l_pcie_top_v1_8.v:490–495`、`ips2l_pcie_hard_ctrl_v1_8.v:650–655` | button/power-up/perst进硬核；CORE_RST_N/TRAINING_RST_N从硬核出来。training reset与core reset为不同信号，不应混用；CORE_RST_N产生条件在硬核primitive内部。 |
| `V/rtl/fpga_v8_cooperative_top_v2_rfg01.v:355–358,442–455` | AXI reset=`~ddr_init_done`，不由pci core_rst_n直接驱动；guard同时观察两个域reset及link。 |
| `V/rtl/fpga_v8_pcie_fifo_h2f_tc02.v:90–112` | 明确要求 COORDINATED PCIe + AXI fabric/endpoint reset；独立link/CPU reset不支持pending-DMA清理。handshake epoch使用AXI或PCIe reset，并不意味着AXI writer/crossbar全部跟随PCIe reset。 |
| `V/rtl/fpga_v8_reset_fault_guard_02.v:25–36,44–75` | runtime_active后健康状态下降置persistent fault；fault只初始化为0，没有局部复位清除路径。admission关闭不是drain，更不是可观察idle接口。 |

**appcore 判定：** 如果 SBR确实导致该硬核core_rst_n下降，连接到它的PCIe controller/FIFO域可复位；当前公开资料尚不能认证这个前提。即便前提成立，AXI/DDR域仍不自动清除。若SBR只造成training/link变化，guard仍可能在runtime_active后锁住admission；该锁不是全域事务取消证书。

**额外顺序风险：SRAM重载后再bus reset不一定产生可用新session。** 新镜像若已经完成内部启动qualification、runtime_active=1，随后link/core reset会重新锁存fault，rebind不能解除。即使主机没提交过DMA，runtime_active也可由内部qualification置1。最终link/reset动作必须在镜像允许的启动时序内完成，或接受需要再次完整SRAM重载；不能无证据把“program→任意SBR→rescan”当无害bring-up。

## 4. Rockchip shutdown/reboot：公开实现差异

上游 [v6.1 pcie-dw-rockchip.c](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/controller/dwc/pcie-dw-rockchip.c#L165) `165–186` start_link通过optional reset GPIO作logical0→等待100ms→logical1；`242–247` 使用 `devm_gpiod_get_optional(...,"reset",GPIOD_OUT_HIGH)` 及reset control。GPIO descriptor逻辑值依active-low属性转换，不能照抄为物理PERST低→高。完整liveDT无reset-gpios时，正常OF optional获取没有该GPIO；代码存在不证明此板实际有对应toggle。

上游同文件 `360–368` platform_driver只有probe，**没有remove/shutdown callback**。不能从probe PERST代码推论普通reboot会执行它；也不能拿 [`pcie-rockchip-host.c`](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/controller/pcie-rockchip-host.c#L1042) 的rk3399匹配、remove资源释放路径作为当前rk3568 DW控制器依据。

公开 Rockchip [`develop-6.1/pcie-dw-rockchip.c`](https://github.com/rockchip-linux/kernel/blob/develop-6.1/drivers/pci/controller/dwc/pcie-dw-rockchip.c#L1862)（本次下载内容hash见末尾，仅作差异样本，**未绑定当前6.1.99内核，branch URL可变**）：

- `692–705` optional reset GPIO以GPIOD_OUT_LOW取得，并有perst-inactive-ms默认200；与上游不同。
- `1862–1872` shutdown将bus软件current_state标D3cold、disable LTSSM、mask interrupt；**此函数未toggle GPIO、未regulator_disable、未reset_control_assert**。软件D3cold标记不是物理断电证明。
- `1781–1845` remove调用host_deinit、host_unconfig、hardware_io_unconfig及PM释放；`.shutdown=rk_pcie_shutdown`、`.remove=rk_pcie_remove` 是不同callback，不能拿remove的动作证明reboot发生相同动作。

上游 [pci-driver.c:505–524](https://github.com/torvalds/linux/blob/v6.1/drivers/pci/pci-driver.c#L505) 普通shutdown可调用endpoint驱动shutdown；通用 `pci_clear_master` 明确受kexec_in_progress条件控制。其“firmware big hammer”注释只是平台假设，不能用作本RK warm reboot强制清DMA的现场证明。[drivers/base/core.c:4611–4678](https://github.com/torvalds/linux/blob/v6.1/drivers/base/core.c#L4611) shutdown遍历调用shutdown而非统一remove。

所以当前还缺：运行下游controller的精确源/补丁及其shutdown、后续bootloader/复位/PHY初始化、endpoint probe重新设BME的时间关系。公开源码足以否定“Linux普通reboot天然togglePERST/clearsendpointAXI”的默认结论，不足以否定实际平台存在可合格reset时序。

## 5. 可审核的未来真实 rebuild 顺序（不是执行记录）

目标是失效旧 session、重建 host allocator/IRQ/driver 和完整 FPGA fabric 会话；旧事务取消/丢弃，不追认成功或drained。无需虚构idle寄存器，不把两板物理断电设为唯一原理。以下每步必须在真实执行后记录结果；本报告不签accepted、不制作producer。

1. **冻结旧提交入口。** 保留boot、owner及可能受影响pages、最后请求/方向/地址/长度、fixed身份；阻止用户和驱动自动提交。当前已无owner是保存事实，不能追认过去free安全。不能以open设备、kill owner、rmmod或driver unbind作为第一步，它们可能释放旧pages。
2. **先明确禁止bus mastering，再initial bus reset。** 负责人使用已有受控配置接口清Command BME，只读确认BME-；此处是未来硬件变更，本文不提供盲运行脚本。随后调用已确认作用域和下游实现的endpoint bus reset；保存入口BME、reset返回、父桥/作用域和返回后BME。排除reset回调/提交路径恢复BME。依据硬核表2-23，此时MEM/IO新请求禁止；不填dma_idle=true。该reset不是完整AXI清理的替代品。
3. **RK reboot之前闭合连续隔离。** 从旧pages可能复用之前，直至完整SRAM重载覆盖旧描述符/AXI状态，必须有真实依据保证旧endpoint不能向复用host地址发DMA。可以是已经解析owner的既有reset/link控制及确定boot时序，或可核验的BME持续禁止机制。不能只凭reset返回、BME一次读回、TransPend-、linkdown某个瞬时值、等待几秒就宣布跨boot隔离成立。initial SBR已有TLP与RC队列如何在host reset边界丢弃/终止也应属于此实际平台论证，而非追认drain。
4. **RK reboot建立新boot/allocator，再qualified完整SRAM重载。** 若采用用户提出的该顺序，必须特别排除新内核pango probe在SRAM重载前执行pci_set_master，旧endpoint保留描述符并重新写新内存的窗口。新boot起来后才补清BME，无法修复此前窗口。仅在这项连续隔离被证实时，此顺序才可认证；否则该顺序保持blocked，需审查使用既有reset保持或调整完整重载位置的可行时序，不擅自新增脚本/consumer规则。重载应覆盖PCIe用户引擎、FIFO、AXI/crossbar/DDR接口及持久guard状态，保留镜像SHA、vendor编程成功/DONE真实日志。
5. **最终link/reset/rescan/rebind按guard启动边界安排。** 不默认sysfs bus reset toggle PERST。若此硬核必须外部PERST而当前接口未解析，停在此blocked理由；rescan无法补硬件复位。若实证SBR能满足硬核bring-up，则还须解决第3节guard在重载后再SBR可能锁fault的顺序。remove/rescan只更新枚举，不做全域取消；driver bind/probe可能重新设BME，应只在旧fabric状态已被完整替换、IRQ/描述符/新buffer初始化适当时开放。记录0755实际新BDF、resource/link/MSI、新loaded build-id及driver bind；不假定BDF不变。
6. **审核后开启新session。** 保存同次action、boot_before/after、真实重枚举/rebind及上述连续隔离/完整重载时序证据；旧fd/mmap/IRQ计数/lease/bank描述符作废，不跨会话复用。按已有generation合同重建；后续数据面另行授权。不绕过现有consumer的owner preflight，不将reboot伪装物理cold power，不用DMA读状态来制造idle证明。

## 6. 当前 blocked reason 与待补的最小证据

**blocked reason不是“必须有全域idle寄存器”或“只能两板掉电”。** 已有硬核BME禁MEM/IO依据，可走reset取消旧会话方向；但目前缺少以下具体因果连接：

- 实际6.1.99 endpoint bus方法究竟走父桥SBR还是slot/downstream hook；实际父桥作用域与驱动reset callbacks。
- SBR对本Pango CORE_RST_N/TRAINING_RST_N的时序及对AXI未复位状态的处理。现有frozen源码已证明单独PCIe reset不等于完整AXI reset，完整SRAM重载仍承担全fabric失效。
- GPIO144真实provider/consumer和vpcie3v3 phandle0x140所有权。缺reset-gpios不证明没有板级PERST线路，却阻止把GPIO144直接归因给此rootport。
- **initial BME- + reset 到RK重启、新probe、SRAM重载完成之间的连续隔离证据**；尤其旧BME恢复/新probe设master先于SRAM的窗口，以及RC旧队列在平台复位边界的处理。
- 最后SBR/PERST与新镜像guard qualification的兼容顺序；避免完整重载之后再次制造persistent fault。

主会话后续只读解析DT/provider及实际source provenance可缩小缺口；完整执行认证最终需要真实操作时序记录或绑定此平台的确定源码/硬核规格。不得用本报告文字替代操作事实，也不要求凭空新增硬件空闲门禁。

## 7. 新核查文件身份与公开源码

| 本地 frozen文件（相对V） | SHA256 |
|---|---|
| `rtl/fpga_v8_pango_pcie_top_h2f_rfg01.v` | `2a36809233007d09b0f4583bfcaaed4876f56b54fa4802cec36c07edc1225351` |
| `rtl/fpga_v8_cooperative_top_v2_rfg01.v` | `ca02da78385c7b9f156373748c5e46cc47f9a104b006778a99a35200d2991841` |
| `rtl/fpga_v8_reset_fault_guard_02.v` | `e5a61f4085c4691387c10a8000aa74eb1c50c0ad3ee1a2d12f3a48d74038e9dd` |
| `inputs/ipcore/pcie_test/pcie_test.v` | `a8e162628aa9f4bc473a591bc28e7a60524de3956d4201ba114cd293e1a030c9` |
| `inputs/ipcore/pcie_test/rtl/ips2l_pcie_top_v1_8.v` | `31ee1ae2722dfd9006961f490aa5218d1ae3675427743d355ff61b0357debba5` |
| `inputs/ipcore/pcie_test/rtl/ips2l_pcie_hard_ctrl_v1_8.v` | `ed4c6da3518ae16d11c3079c193c0e87c459ae383444ffb6e2b0eb3abd93d2c1` |

公开源码下载仅在内存核查，不落新tool/source文件；行号对应此次原文。

| 公开源版本/文件 | SHA256 |
|---|---|
| torvalds/linux v6.1 `drivers/pci/pci.c` | `fa49971ce6fe0f25ad234f1aef64328adddb4cdaca6081f6665e9c16e7d45d2d` |
| 同tag `drivers/pci/pci-sysfs.c` | `8e64db07837d2ada06e2ab301101d561e4e7544a134fe6d9746e363afe296a55` |
| 同tag `drivers/pci/pci-driver.c` | `50b917a3082a9bec51295ad040d0d2d820cbaa4f00cac9ba92351d735e361eb9` |
| 同tag `drivers/base/core.c` | `0ac6e5f7621f1eb5a2faf957b86c18d83065773bf48a8df297b1d3e628d9386a` |
| 同tag `drivers/pci/controller/dwc/pcie-dw-rockchip.c` | `01c464343a5acfc11d27575bfea2a5155f7b46be1bdad73e6d595287b06dd98e` |
| 同tag `drivers/pci/controller/pcie-rockchip-host.c` | `3c650dcfc1695b0b5e93143381f2b9127bc37a3daeae7b51a7abf22ce0a24d40` |
| rockchip-linux/kernel develop-6.1 `drivers/pci/controller/dwc/pcie-dw-rockchip.c`（可变branch参考，非actual身份） | `be6a07769c33c6b7b6942ef65d552f297e2c6866880fb062b760ad9120b8f2b6` |
