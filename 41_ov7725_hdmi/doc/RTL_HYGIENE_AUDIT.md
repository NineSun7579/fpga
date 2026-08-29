# OV7725 O1-A RTL 卫生修复评审

状态：O1-A 评审与 O1-B 实现均已完成；O2/RDC 与 O1-C/H3 仍未完成

适用日期：2026-08-29

适用工程：`41_ov7725_hdmi`

## 1. 目标与边界

本评审为 PDS 2022.2-SP6.4 完整构建日志中的 39 条项目手写 RTL `Verilog-2019` 位宽告警建立逐项归属，并确定隐式网络与 serializer 复位的最小修改契约。

本批只新增文档，不修改：

- `rtl/**`；
- `prj/ipcore/**` 厂商生成文件；
- FDC、RCF 或 IDF；
- `build/**` 生成物。

O1-A 不处理 O0-A 已识别的 CDC/RDC、FIFO 分侧复位、时序例外或板级 I/O delay。这些问题仍属于 O2、O3、O4 和 H3。

## 2. 事实来源

| 事实 | 一手来源 |
|---|---|
| 39 条手写 RTL 位宽告警 | `build/logs/pds-gen_bit_stream.log` |
| DDR3 AXI、APB、memory 和 debug 端口宽度 | `prj/ipcore/ddr3_ip/ddr3_ip_tmpl.v`、`ddr3_ip.v` |
| DDR3 行地址和控制器地址配置 | `prj/ipcore/ddr3_ip/ddr3_ip.idf` |
| 第 15 根地址脚约束 | `prj/source/ov7725_hdmi.fdc` |
| `mem_a[14]` 当前实现结果 | `build/pds/synthesize/ov7725_hdmi_syn.vm` |
| OSERDES `RST` 极性 | PDS SP6.4 `GTP_OSERDES_E2.v` 与官方 PG2L100H LVDS 示例 |
| 顶层隐式网络及 serializer 复位链 | 当前 `rtl/**` |

厂商生成源码和已安装 PDS 文件只作为接口事实，不属于 O1-B 修改对象。

## 3. 结论摘要

39 条告警分布为：

| 文件与实例位置 | 数量 | 结论 |
|---|---:|---|
| `ov7725_dri/ov7725_dri.v:72` | 1 | 8-bit 寄存器地址应显式零扩展到 16 bit |
| `ddr3_ctrl_top/ddr3_ctrl_top.v:153` | 4 | 保留地址/长度左移 3 的协议语义，但显式选择可容纳的源位 |
| `ddr3_ctrl_top/ddr3_ctrl_top.v:200` | 26 | 25 个定宽 tie-off；`mem_a` 1 项受板级事实阻断 |
| `ov7725_hdmi.v:133` | 6 | 为地址、burst 常量或切片显式零扩展 |
| `hdmi_top/serializer_10_to_1.v:35/80` | 2 | 使用高有效 serializer reset，替代无尺寸常量 `0` |
| 合计 | 39 | 38 条可在 O1-B 确定修复，1 条转入 H3/O1-C |

除 39 条日志告警外，顶层还有两个隐式网络：

- `rst_n`：有实际扇出，O1-B 显式声明；其组合生成和跨域使用不在本批重构。
- `sys_init_done`：只有赋值，没有读取者，O1-B 删除无效赋值。

## 4. 39 条位宽告警逐项归属

表中“actual 宽度”按 Verilog-2001 表达式规则和当前声明计算。无尺寸十进制常量 `0/1` 在当前 PDS 日志中按 32 bit 报告。

| # | 位置 | 实例端口 | 当前 actual | formal | O1-B 决策 |
|---:|---|---|---:|---:|---|
| 1 | `ov7725_dri.v:72` | `i2c_dri.i2c_addr` | `i2c_data[15:8]`，8 | 16 | `{8'b0, i2c_data[15:8]}` |
| 2 | `ddr3_ctrl_top.v:153` | `aq_axi_master.wr_adrs` | `{wd_addr,3'd0}`，30 | 27 | `{wd_addr[23:0],3'b000}` |
| 3 | `ddr3_ctrl_top.v:153` | `aq_axi_master.wr_len` | `{wd_len,3'd0}`，13 | 11 | `{wd_len[7:0],3'b000}` |
| 4 | `ddr3_ctrl_top.v:153` | `aq_axi_master.rd_adrs` | `{rd_addr,3'd0}`，30 | 27 | `{rd_addr[23:0],3'b000}` |
| 5 | `ddr3_ctrl_top.v:153` | `aq_axi_master.rd_len` | `{rd_len,3'd0}`，13 | 11 | `{rd_len[7:0],3'b000}` |
| 6 | `ddr3_ctrl_top.v:200` | `ddr3_ip.axi_awuser_ap` | `0`，32 | 1 | `1'b0` |
| 7 | `ddr3_ctrl_top.v:200` | `ddr3_ip.axi_awuser_id` | `0`，32 | 4 | `4'd0` |
| 8 | `ddr3_ctrl_top.v:200` | `ddr3_ip.axi_aruser_ap` | `0`，32 | 1 | `1'b0` |
| 9 | `ddr3_ctrl_top.v:200` | `ddr3_ip.axi_aruser_id` | `0`，32 | 4 | `4'd0` |
| 10 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_clk` | `0`，32 | 1 | `1'b0` |
| 11 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_rst_n` | `0`，32 | 1 | `1'b0` |
| 12 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_sel` | `0`，32 | 1 | `1'b0` |
| 13 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_enable` | `0`，32 | 1 | `1'b0` |
| 14 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_addr` | `0`，32 | 8 | `8'd0` |
| 15 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_write` | `0`，32 | 1 | `1'b0` |
| 16 | `ddr3_ctrl_top.v:200` | `ddr3_ip.apb_wdata` | `0`，32 | 16 | `16'd0` |
| 17 | `ddr3_ctrl_top.v:200` | `ddr3_ip.mem_a` | `mem_a[14:0]`，15 | 14 | 阻断：转 H3/O1-C |
| 18 | `ddr3_ctrl_top.v:200` | `ddr3_ip.dbg_gate_start` | `0`，32 | 1 | `1'b0` |
| 19 | `ddr3_ctrl_top.v:200` | `ddr3_ip.dbg_cpd_start` | `1`，32 | 1 | `1'b1` |
| 20 | `ddr3_ctrl_top.v:200` | `ddr3_ip.dbg_ddrphy_rst_n` | `1`，32 | 1 | `1'b1` |
| 21 | `ddr3_ctrl_top.v:200` | `ddr3_ip.dbg_gpll_scan_rst` | `0`，32 | 1 | `1'b0` |
| 22 | `ddr3_ctrl_top.v:200` | `ddr3_ip.samp_position_dyn_adj` | `0`，32 | 1 | `1'b0` |
| 23 | `ddr3_ctrl_top.v:200` | `ddr3_ip.wrcal_position_dyn_adj` | `0`，32 | 1 | `1'b0` |
| 24 | `ddr3_ctrl_top.v:200` | `ddr3_ip.force_read_clk_ctrl` | `0`，32 | 1 | `1'b0` |
| 25 | `ddr3_ctrl_top.v:200` | `ddr3_ip.init_slip_step` | `0`，32 | 16 | `16'd0` |
| 26 | `ddr3_ctrl_top.v:200` | `ddr3_ip.init_read_clk_ctrl` | `0`，32 | 12 | `12'd0` |
| 27 | `ddr3_ctrl_top.v:200` | `ddr3_ip.debug_cpd_offset_adj` | `0`，32 | 1 | `1'b0` |
| 28 | `ddr3_ctrl_top.v:200` | `ddr3_ip.debug_cpd_offset_dir` | `0`，32 | 1 | `1'b0` |
| 29 | `ddr3_ctrl_top.v:200` | `ddr3_ip.debug_cpd_offset` | `0`，32 | 10 | `10'd0` |
| 30 | `ddr3_ctrl_top.v:200` | `ddr3_ip.ck_dly_en` | `1`，32 | 1 | `1'b1` |
| 31 | `ddr3_ctrl_top.v:200` | `ddr3_ip.init_ck_dly_step` | `0`，32 | 8 | `8'd0` |
| 32 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.addr_rd_min` | `0`，32 | 27 | `APP_ADDR_MIN` |
| 33 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.addr_rd_max` | `APP_ADDR_MAX[26:1]`，26 | 27 | `{1'b0, APP_ADDR_MAX[26:1]}` |
| 34 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.rd_burst_len` | `H_CMOS_DISP[10:2]`，9 | 10 | `{1'b0, H_CMOS_DISP[10:2]}` |
| 35 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.addr_wd_min` | `0`，32 | 27 | `APP_ADDR_MIN` |
| 36 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.addr_wd_max` | `APP_ADDR_MAX[26:1]`，26 | 27 | `{1'b0, APP_ADDR_MAX[26:1]}` |
| 37 | `ov7725_hdmi.v:133` | `ddr3_ctrl_top.wd_burst_len` | `H_CMOS_DISP[10:2]`，9 | 10 | `{1'b0, H_CMOS_DISP[10:2]}` |
| 38 | `serializer_10_to_1.v:35` | master `GTP_OSERDES_E2.RST` | `0`，32 | 1 | 高有效 `reset` |
| 39 | `serializer_10_to_1.v:80` | slave `GTP_OSERDES_E2.RST` | `0`，32 | 1 | 高有效 `reset` |

## 5. 地址与 burst 的协议语义

`ddr3_rw_ctrl` 与 `aq_axi_master` 之间的左移 3 不能简单删除。手写 RTL 能证明编码关系，但没有给出足以确认物理字节单位的接口规格：

- `ddr3_rw_ctrl` 产生当前控制器地址计数值，并按配置的长度值推进；
- `aq_axi_master` 接收低 3 位为 0 的编码地址；O1-B 只保留该 legacy 编码，不把低 3 位解释成未经规格确认的字节偏移；
- `aq_axi_master` 使用 `wr_len[10:3]` 和 `rd_len[10:3]` 还原输入长度值；
- 当前 `H_CMOS_DISP=640`，`H_CMOS_DISP[10:2]=160`，编码后长度为 1280，能放入 11 bit。

当前 `wd_addr/rd_addr[26:24]` 由 `ddr3_rw_ctrl` 固定为 `3'b000`，因此显式连接低 24 bit 后追加 3 个 0 与现有有效行为一致。当前 burst 160 小于 256，因此显式使用低 8 bit 后追加 3 个 0 也与现有有效行为一致。

O1-B 必须在注释中记录以下接口假设：

- AXI 地址源不得超过 24 bit，否则左移 3 会溢出 27-bit formal；
- 编码前的 `wd_len/rd_len` 值必须小于等于 255；
- 这些上界由当前参数和编译检查证明，不得只依赖截断行为。

由于工程仍是 Verilog-2001，O1-B 不为这一小批次改写成 SystemVerilog assertion。最低机器证据为 PDS elaboration、定向参数扫描和现有参数值检查；未来迁移 SystemVerilog 时再加入 elaboration assertion。

## 6. `mem_a` 冲突与停止条件

活动 DDR3 IP 的一致证据为 14-bit row address：

- IDF：`MEM_ADDR_WIDTH=14`、`DDR3_MEM_ROW_WIDTH=14`、`MEM_ROW_WIDTH=14`；
- 生成模块：`mem_a[13:0]`；
- template：`mem_a[13:0]`；
- 综合网表：IP 只驱动顶层 `mem_a[13:0]`。

但手写顶层与 FDC 又定义了第 15 根地址线：

- `ov7725_hdmi.v` 与 `ddr3_ctrl_top.v` 声明 `mem_a[14:0]`；
- FDC 将 `mem_a[14]` 约束到 `V3`；
- 当前综合网表把 `mem_a[14]` 固定为 `1'b0`。

因此不能只为清除 warning 把端口收窄。H3 必须提供 DDR3 完整料号、组织和原理图：

- 若器件只需 A0..A13：在独立 O1-C 批次同时收窄两层 RTL，并删除 FDC 的 `mem_a[14]` 约束；
- 若器件需要 A0..A14：使用 SP6.4 IP Compiler 重生成 15-bit row 的 DDR3 IP，并同步审核控制器地址宽度、FDC 和板级映射。

H3 未关闭前，O1-B 保留这一条精确告警，gate 只能对白名单中的 `ddr3_ip.mem_a` 单项放行；任何其他手写 RTL 位宽告警均失败。

## 7. 隐式网络决策

### 7.1 `rst_n`

`ov7725_hdmi.v` 通过：

```verilog
assign rst_n = sys_rst_n & clk_locked;
```

隐式创建 1-bit wire，并送往 camera、DDR3 和 HDMI 路径。O1-B 只增加显式 `wire rst_n;`，不改变组合生成式。

该信号参与多个时钟域的复位释放，属于 O0-A 已记录的 RDC 风险。逐域异步置位、同步释放必须留到 O2，不能在 O1-B 顺带修改。

### 7.2 `sys_init_done`

`sys_init_done` 只有：

```verilog
assign sys_init_done = ddr3_init_done;
```

仓库中没有读取者。O1-B 删除该赋值，不新增一个未使用的显式 wire。

O1-B 不在顶层启用跨文件生效的 ``default_nettype none``，避免改变厂商文件和历史编译单元的解析范围；后续可以在独立 lint/语言治理批次引入并验证。

## 8. Serializer reset 决策

当前复位链为：

```text
sys_rst_n & ddr3_init_done
  → asyn_rst_syn.reset_n（低有效输入）
  → asyn_rst_syn.syn_reset（高有效输出）
  → dvi_transmitter_top.reset
  → serializer_10_to_1.reset_n（名称错误，当前未使用）
```

PDS SP6.4 仿真模型声明 `GTP_OSERDES_E2.RST` 为 1 bit，并直接送入本地复位。官方 PG2L100H LVDS 示例把低有效 `tx_gtp_rstn` 取反后接到 `RST`，证明 `RST` 高有效。

O1-B 的最小正确修改为：

1. 将 `serializer_10_to_1.reset_n` 重命名为高有效 `reset`；
2. 更新 `dvi_transmitter_top` 的四个命名端口连接；
3. master/slave OSERDES 都连接 `.RST(reset)`；四个 serializer 共八个 OSERDES 实例会获得本地复位，日志只按模块定义中的两个结构位置报告；
4. 添加简短 VSCS 接口注释，说明复位高有效、相对 serializer 时钟的行为由原语 `ASYNC_RESET` 参数决定。

该修改会把原来永久不复位的 OSERDES 改为受控复位，属于局部功能修复，不只是排版变更。复位极性和意图已有一手依据；相对 `pclk_x5` 的最终释放方法仍须在 O2/RDC 检查中复核。未经 O1-A 审核不得实施。

## 9. O1-B 最小修改清单

O1-B 只修改以下文件：

| 文件 | 修改 |
|---|---|
| `rtl/ov7725_dri/ov7725_dri.v` | 16-bit I2C 地址显式零扩展 |
| `rtl/ddr3_ctrl_top/ddr3_ctrl_top.v` | 4 个地址/长度编码、25 个 DDR3 IP 定宽 tie-off；保留 `mem_a` 冲突 |
| `rtl/ov7725_hdmi.v` | 显式声明 `rst_n`、删除 `sys_init_done`、修正 6 个定宽连接 |
| `rtl/hdmi_top/serializer_10_to_1.v` | 将端口定义为高有效 `reset`，连接两个 OSERDES `RST` |
| `rtl/hdmi_top/dvi_transmitter_top.v` | 更新四个 serializer 命名端口 |
| `scripts/check_build.ps1` | 将基线从 39 条改为仅允许精确的 `ddr3_ip.mem_a` 1 条 |
| README、实施记录、TODO、`.nexus-map` | 同步验证结果和剩余阻断 |

O1-B 不修改：

- `mem_a` 端口宽度、DDR3 IDF 或 FDC；
- CDC/RDC 结构；
- FIFO 生成文件；
- 时钟关系或时序例外；
- 历史第三方版权/来源头。

后续新增或修改的设计意图注释遵循 VSCS，重点记录地址单位、burst 上界和 reset 极性。由于这些文件含历史第三方来源头且尚未完成全模块治理，O1-B 不声明文件整体符合 VSCS。

## 10. O1-B 回归与完成定义

静态检查：

1. 修改仅位于第 9 节列出的范围；
2. 厂商 `prj/ipcore/**` 哈希不变；
3. `git diff --check` 通过；
4. PowerShell AST 无解析错误；
5. 新注释不维护作者、日期或重复端口声明，不作无证据的安全保证。

PDS 回归：

```powershell
powershell -ExecutionPolicy Bypass -File .\41_ov7725_hdmi\scripts\run.ps1 `
    -Action clean-build
powershell -ExecutionPolicy Bypass -File .\41_ov7725_hdmi\scripts\run.ps1 `
    -Action build `
    -RunTo compile
```

compile 验收：

- PDS 退出码为 0，日志无 `^E:`；
- 原 38 条确定性手写 RTL 位宽告警消失；
- 只允许 `ddr3_ctrl_top.v:ddr3_ip.mem_a` 这一条已记录告警；
- 不新增隐式网络、端口、截断或未分类 warning；
- 顶层、16 个手写 RTL、4 个 IDF 和唯一 FDC 不变。

随后从空 `build/` 执行七阶段完整回归。因 O0-A 的 CDC/RDC 和负时序尚未修复，严格 gate 仍应失败；显式 baseline gate 只能在已知时序端点和单一 `mem_a` warning 精确匹配时通过，并继续输出不可发布标记。

O1-B 实测结果：

- compile 与七阶段实现的 PDS 退出码均为 0，完整日志无 `E:`；
- 手写 RTL 位宽告警由 39 条降为 1 条，唯一剩余项为 `ddr3_ip.mem_a`；
- 完整日志 warning 由 O0-B 的 4105 条降为 4067 条，critical 保持 81 条且没有新增未分类项；
- 综合网表、PNR 网表、slow-corner SDF、`.sbit` 和 `.bin` 均存在且非零；
- 严格 gate 返回 1，baseline gate 在精确匹配 7 组失败指纹后返回 0，并明确输出不可发布标记。

接入八个 OSERDES 的 `RST` 后，最终 STA 新增一组 Slow/Recovery：`pixel_clk → pixel_clk_5x`、WNS `-0.643 ns`、TNS `-4.191 ns`、8/8 端点。详细报告将 startpoint 指向 `reset_syn/reset_1`，八个 endpoint 对应四个 serializer 的 master/slave OSERDES。该组只作为当前失败状态指纹进入 baseline，不构成 waiver；O2-B 必须通过 `pixel_clk_5x` 域同步释放复位关闭它。

QuestaSim 当前不可用，因此 O1-B 不能声明 HDMI 串化功能或四级仿真通过。OSERDES reset 的动态行为必须在 S0/S3 就绪后补测。

## 11. 回退边界

- I2C、DDR tie-off、顶层常量和 serializer reset 分文件提交前可分别审阅，但 O1-B 最终作为一个功能一致的 RTL 卫生批次提交。
- 若 compile 出现新 warning，先回退对应文件的小组修改，不改厂商 IP 消警。
- 若连接 OSERDES reset 导致实现或时序结果发生非预期变化，保留 O1-A 决策文档，回退 serializer 两文件并单独分析；不得把 `RST` 再绑无尺寸常量。
- `mem_a` 的任一修改必须进入 H3/O1-C 独立批次，不能混入 O1-B。

## 12. O1-A 完成定义

O1-A 只有在以下条件同时满足时完成：

1. 39 条告警数量和分组可由当前 SP6.4 日志复现；
2. 每条告警均具有 actual/formal 宽度、一手依据和处置方向；
3. `mem_a` 冲突被明确标为板级阻断，而非擅自选择 14 或 15 bit；
4. 隐式网络与 OSERDES reset 的功能语义已明确；
5. O1-B 修改清单、回归命令、停止条件和回退边界无需再次猜测；
6. O1-A 本身没有修改 RTL、IP 或约束。

## 13. O1-B 完成与后续边界

O1-B 已完成以下事实闭环：

1. 38 条确定性位宽告警消失，`mem_a` 保持为唯一板级阻断；
2. `rst_n` 显式声明，`sys_init_done` 死网删除；
3. 四个 serializer 的八个 OSERDES 均连接高有效本地复位；
4. gate 同时检查参数上界、唯一 `mem_a` 告警和 7 组精确时序失败签名；
5. 厂商 IP、FDC、RCF、FIFO 和时序例外未修改；
6. QuestaSim 未安装，因此没有声明行为级、综合后或 PNR 后仿真通过。

下一批必须先做 O2-A 契约确认，再以独立 O2-B 提交把 OSERDES reset 的释放同步到 `pixel_clk_5x`。不得把 O2-B 扩展为顶层、camera、DDR UI 或 FIFO 的全量复位重构；这些属于 O2-C。
