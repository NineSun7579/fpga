# DDR3 D3-A 端口与层级映射

状态：只读核对，等待 D3-A 用户审核。更新日期：2026-08-30。

本文件把活动 DDR3 core、现有 `test_ddr` wrapper 与 D2 有限自检契约对齐。它不实现 BIST，不修改厂商生成文件，也不改变任何物理端口。

## 证据范围

| 事实 | 证据 |
|---|---|
| 公开 core 模块为 `ddr3` | `ip_core/ddr3/ddr3.v:12` |
| 现有物理 wrapper 为 `test_ddr` | `ip_core/ddr3/example_design/rtl/test_ddr.v:12` |
| core 实例名固定为 `I_ips_ddr_top` | `test_ddr.v:746` |
| D3-A 仅允许新增项目自有 top/BIST | `doc/FINITE_SELF_TEST_CONTRACT.md`、项目 README |

## 参数与宽度

当前活动 core 默认参数为：

| 参数 | 当前值/公式 | 影响 |
|---|---:|---|
| `MEM_ROW_WIDTH` | 15 | `mem_a[14:0]` |
| `MEM_COLUMN_WIDTH` | 10 | 控制器地址组成 |
| `MEM_BANK_WIDTH` | 3 | `mem_ba[2:0]` |
| `MEM_DQ_WIDTH` | 16 | `mem_dq[15:0]`、128-bit 用户数据 |
| `MEM_DM_WIDTH` | 2 | `mem_dm[1:0]` |
| `MEM_DQS_WIDTH` | 2 | 两个 DQS/DQS_n byte lane |
| `CTRL_ADDR_WIDTH` | `15 + 10 + 3 = 28` | `axi_awaddr`/`axi_araddr[27:0]` |

`axi_wdata` 和 `axi_rdata` 均为 `8 * MEM_DQ_WIDTH = 128` bit；`axi_wstrb` 为 16 bit。地址单位尚未从 IP 文档或板级资料独立确认，D3-A 不得自行改成 byte、word 或 burst 地址。

## 用户接口映射

### 写地址

| 端口 | 宽度 | D3-A 语义 |
|---|---:|---|
| `axi_awaddr` | 28 | 单 beat pair 的地址输入 |
| `axi_awuser_ap` | 1 | 保持为 0，除非 IP 文档证明需要 APB/特权语义 |
| `axi_awuser_id` | 4 | 固定单一 ID，建议 0 |
| `axi_awlen` | 4 | 有限 BIST 使用单 beat，建议 0 |
| `axi_awvalid` | 1 | 发起地址握手 |
| `axi_awready` | 1 | core 接受地址的返回握手 |

地址接受条件固定为 `axi_awvalid && axi_awready`。

### 写数据

| 端口 | 宽度 | D3-A 语义 |
|---|---:|---|
| `axi_wdata` | 128 | 确定性测试数据 |
| `axi_wstrb` | 16 | 单 beat 全字节有效时为全 1 |
| `axi_wready` | 1 | 活动 IP 的写数据接受/完成指示 |
| `axi_wusero_id` | 4 | 返回 ID，记录但不作为成功唯一条件 |
| `axi_wusero_last` | 1 | 返回 beat 结束标记 |

该接口不是完整 AXI4：core 没有独立的 `axi_wvalid` 输入。D3-A 必须按已观察到的 `axi_wready` 语义设计 watchdog 和完成判定，不得套用标准 AXI4 W/B 通道假设。

### 读地址与返回

| 端口 | 宽度 | D3-A 语义 |
|---|---:|---|
| `axi_araddr` | 28 | 单 beat pair 的读地址 |
| `axi_aruser_ap` | 1 | 保持为 0，除非 IP 文档另有证明 |
| `axi_aruser_id` | 4 | 固定单一 ID，建议 0 |
| `axi_arlen` | 4 | 有限 BIST 使用单 beat，建议 0 |
| `axi_arvalid` | 1 | 发起读地址 |
| `axi_arready` | 1 | core 接受读地址 |
| `axi_rdata` | 128 | 返回数据 |
| `axi_rid` | 4 | 返回 ID |
| `axi_rlast` | 1 | 返回 beat 结束标记 |
| `axi_rvalid` | 1 | 返回数据有效 |

读地址接受条件固定为 `axi_arvalid && axi_arready`。读返回以 `axi_rvalid` 和 `axi_rlast` 为边界；接口没有 `axi_rready`，因此 BIST 必须自行限制 outstanding 数量并设置读 watchdog。

## 时钟、复位与物理边界

- `ref_clk` 连接现有 wrapper 的 `free_clk`；core 输出 `core_clk` 供 BIST 状态机使用。
- wrapper 形成 `resetn = dbg_ddr_rst_n & rst_board`，随后由 `core_clk_rst_n` 同步释放；D3-A 不应绕过该复位链。
- `ddr_init_done` 是等待 DDR 初始化完成的公开状态；有限测试只能在其有效后启动。
- APB 端口在当前 wrapper 中全部绑 0 或悬空，不属于 D3-A BIST 接口，禁止借此新增物理端口。
- DDR3 物理端口、FDC/RCF 和 `I_ips_ddr_top` 实例名必须保持不变。

## D3-A 允许范围

1. 新增项目自有 `rtl/ddr3_bringup_top.sv` 与 `rtl/ddr3_finite_bist.sv`。
2. 将 BIST 连接到上述公开 `ddr3` 接口，并在 `ddr_init_done` 后启动一次有限测试。
3. 首轮只做 compile/elaboration；不实现随机测试、不改 burst/ID 语义、不修改厂商 `ip_core/ddr3/**`。
4. 若端口宽度、地址单位、`axi_wready` 完成语义或 `I_ips_ddr_top` 层级发生变化，立即停止并重新审核。

## 待审核问题

- `axi_awaddr`/`axi_araddr` 的 byte/word 地址单位仍需 IP 文档或用户确认。
- `axi_wready` 是否表示单 beat 数据已写入、以及 `axi_wusero_last` 的必要性，需要在 D3-A 首轮 compile/elaboration 后结合实现日志确认。
- `ddr_init_done` 的复位后稳定时序和 core_clk 频率属于 IP 事实；不得由 BIST 逻辑猜测。
