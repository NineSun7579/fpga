# main OV5640→PCIe Endpoint 接入合同

更新日期：2026-09-04
状态：Draft，作为产品顶层接线前的接口冻结记录，不作为 PCIe 链路签核。

当前平台：`RK3568_MES2L100H / PG2L100H-6IFBG484`。本合同中的 `pg2l50h` 文件名和专项证据属于旧 50H 假设下的行为切片，接入 100H 产品顶层前必须重新核验。

## 1. 范围与证据等级

本合同定义 `main_ov5640_pcie` 的 camera TX 路径如何接入产品 PCIe Endpoint。它只约束
项目自有 adapter 与 Endpoint 用户侧端口的方向、时钟、复位和配置来源，不修改厂商生成
RTL、IDF、FDC/RCF 或 `parallel_driver`。

当前事实来自仓库内的：

- `pcie_dma_test_100h/ipcore/pcie_test/pcie_test.v`：Endpoint 模块端口与方向；
- `pcie_dma_test_100h/ipcore/pcie_test/example_design/bench/pango_pcie_top.v`：示例顶层的
  Endpoint、DMA 和物理端口连接关系；
- `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv`：项目自有边界实现；
- `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv`：等端口行为验证。

专项 TB 的证据等级为 `behavior_verified_with_endpoint_boundary_model`：它证明项目侧到
Endpoint AXIS 子集的接线、握手和字段保持，不证明真实 `pcie_test` 编译、PHY、LTSSM、
串行链路、Root Complex、RK3568 主机内存或板级时序。

## 2. 接入拓扑

```text
OV5640/DVP → camera/DDR3 应用路径 → TX top adapter → PCIe Endpoint
                                      │                 │
                                      │                 ├─ pclk_div2
                                      │                 ├─ core_rst_n
                                      │                 ├─ AXIS0/1/2 ready
                                      │                 └─ cfg/link telemetry
                                      └─ AXIS0/1/2 valid/data/last/user
```

产品顶层只允许存在一套完整 PCIe TX 生成路径。若 Endpoint 内部已经实例化
`ips2l_pcie_dma` 或其 TX top，项目不得再并列实例化第二套完整 TX top；项目侧 camera
请求必须接入已冻结的 Endpoint AXIS-facing 边界，或由产品负责人明确批准另一种唯一拓扑。

## 3. 时钟与复位所有权

| 信号 | 所有者 | 目标域 | 合同 |
|---|---|---|---|
| `endpoint_pclk_div2` | PCIe Endpoint | 完整 TX top 用户域 | 直接驱动 adapter 的 `pcie_clk`；不得由 camera/io 域派生替代 |
| `endpoint_core_rst_n` | PCIe Endpoint | 完整 TX top 用户域 | 直接驱动 adapter 的 `pcie_rst_n`；极性为低有效，释放时序由 Endpoint 负责 |
| `camera_clk/camera_rst_n` | camera/应用顶层 | camera 请求源域 | 只驱动 adapter camera 侧；与 Endpoint 用户域之间必须经过现有 mailbox/CDC |
| `endpoint_smlh_link_up`、`endpoint_rdlh_link_up` | PCIe Endpoint | 观察/产品状态域 | 仅作为遥测透传；本合同不定义掉链取消、重放或 flush |

Endpoint 时钟和复位必须在真实产品顶层由 `pcie_test` 或其唯一产品 wrapper 输出。项目
adapter 不得复制 Endpoint reset synchronizer，也不得把链路状态组合门控到 camera ACK、
AXIS valid 或请求丢弃逻辑。多复位域仍须在 PDS CDC/RDC 和 STA 中独立签核。

## 4. AXIS 通道方向与用途

以下名称采用 `pcie_test` 的 slave 端口语义：Endpoint 输出 `*_tready`，项目向 Endpoint
输入 `*_tvalid/*_tdata/*_tlast/*_tuser`。

| 通道 | 项目侧输出 | Endpoint 侧输入 | 当前用途 |
|---|---|---|---|
| AXIS0 | `endpoint_axis_slave0_tvalid/tdata/tlast/tuser` | `axis_slave0_tready` | CPLD；camera-only 模式必须保持无事务 |
| AXIS1 | `endpoint_axis_slave1_tvalid/tdata/tlast/tuser` | `axis_slave1_tready` | MRD；camera-only 模式必须保持无事务 |
| AXIS2 | `endpoint_axis_slave2_tvalid/tdata/tlast/tuser` | `axis_slave2_tready` | MWR；camera 图像只从此通道进入 Endpoint |

AXIS 的传输资格唯一由 `tvalid && tready` 决定。`tvalid=1` 且 `tready=0` 时，项目必须
保持 `tdata/tlast/tuser` 稳定；ACK 只表示下游 TX 控制器接受请求，不能替代 AXIS beat
握手，也不能被解释为 TLP 已离开 FPGA。

当前 Endpoint slave 端口没有独立 `tkeep`。因此 canonical 路径只向完整 TX top 放行
已经验证的 `keep=4'hf`、单 DWORD、无协议错误请求；partial keep 仍由上层 fail-stop，
不得通过截断或伪造 `tuser` 绕过该边界。

## 5. 配置字段与状态字段

产品顶层从 Endpoint 取得并传给项目 adapter 的配置字段为：

- `cfg_pbus_num[7:0]`；
- `cfg_pbus_dev_num[4:0]`；
- `cfg_max_rd_req_size[2:0]`；
- `cfg_max_payload_size[2:0]`。

这些字段是 Endpoint 配置空间的输出，不由 camera 侧硬编码为设备身份或 payload 能力。
项目 adapter 只把字段转交给已审计 TX top 输入；字段编码、配置空间初始化和主机枚举仍
由真实 Endpoint/IP 资料与产品顶层负责。

`smlh_link_up`、`rdlh_link_up` 在边界中分别输出为 `observed_smlh_link_up`、
`observed_rdlh_link_up`。当前只允许用于状态观察、日志或上层诊断，不允许作为请求准入、
ACK 生成、数据丢弃、自动重放或槽回收条件。

## 6. camera-only 关断清单

`rgb565_pg2l50h_pcie_endpoint_axis_boundary` 当前固定：

- native MWR32/MWR64/MRD32/MRD64 请求为 0；
- MRD、CPLD 和 BAR read 输入为 0 或不连接；
- TX restart 为 0；
- camera MWR32 只经项目 mailbox、仲裁器和完整 TX top 的 AXIS2 输出。

若产品需要恢复 native DMA、配置读写或 RX 处理，必须先形成新的端口合同和独立 TB，不得
在 camera-only wrapper 内静默复用未验证路径。

## 7. 复位、掉链与故障处理

- Endpoint 复位期间，项目不得把未完成 camera 请求伪造成 ACK；现有 mailbox 的 fail-stop
  和在途复位 fault 合同继续有效。
- 任一跨域事务在途时独立复位，事务结果视为不确定；上层必须作废当前 frame/slot，协调
  camera、IO 和 PCIe 域复位后再恢复，不自动重放。
- 链路掉线的取消、重连、重放、主机可见错误和中断语义不在本合同内；在这些语义冻结前，
  `link_up` 只能做遥测。

## 8. 验证与关闭条件

当前专项入口：

`main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_endpoint_axis_boundary.ps1`

已验证：Endpoint reset ownership、AXIS0/1 静默、AXIS2 header 后 payload 背压保持、链路
遥测透传以及 camera MWR32 的 header/data/TLAST。要把本合同从行为边界升格为产品闭环，
还必须取得并验证：

1. 当前 100H 目标下实际使用的 `pcie_test`/产品 Endpoint IP、PHY/refclk/PERST# 和 lane 接线；
2. 完整产品顶层的 RX、DBI/APB、配置、复位和时钟连接；
3. 真实 DDR3 core 与该产品顶层之间的地址单位、初始化、读写完成和槽所有权合同；
4. RK3568 驱动、DMA 缓冲、IOMMU/SMMU、cache 一致性、帧完成和错误恢复协议；
5. PDS CDC/RDC、payload max-delay/bus-skew、STA、综合/PNR/SDF 和板级 golden image 证据。

在上述证据出现前，本合同的结论只能写作“项目 TX path 到 Endpoint AXIS 子集的行为接线
已验证”，不能写作“OV5640→DDR3→PCIe 已完成板级闭环”。
