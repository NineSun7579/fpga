# cam3 SCCB 主机直通 + 补光灯控制（2026-09-26）

## 1. 背景

- 相机 SCL/SDA 只接 FPGA（`cam_scl`/`cam_sda`），RK3568 侧没有任何到相机的 I²C 总线
  （`i2c-6` 只是 HDMI DDC）。原 `ov5640_reg` 只暴露 ACK / CAM_EN / CAM_ADDR_1/2，
  传感器配置表由 FPGA 内部 FSM 上电驱动。
- 因此“配置 cam3 寄存器 / 看 I²C 是否正常 / 点补光灯”必须新增**主机可写 SCCB 直通**。

## 2. 设计

在 `ov5640_reg.v`（video_clk=axi_clk 域）新增 3 个 16 字节对齐寄存器，命令经
`ov5640_top.v` 跨到 `clk_50m`/`dri_clk` 域的 `ov5640.v`，与内建配置 FSM **共用同一
个 i2c_dri 主机**；配置 FSM 用 `cam_init_done` 让位，直通事务只在初始化完成后上总线。

### 2.1 寄存器（CAM3 窗口 0x2000_0400）

| 地址 | 名称 | 属性 | 位定义 |
|---|---|---|---|
| 0x2000_0500 | CAM3_I2C_CMD  | W | [24]=1读/0写, [23:8]=寄存器地址, [7:0]=写数据；写即触发 |
| 0x2000_0510 | CAM3_I2C_RD   | R | [7:0] 最近一次读回字节 |
| 0x2000_0520 | CAM3_I2C_STAT | R | [0]=ack(1=NACK), [1]=done(命令完成，写新命令自清) |

### 2.2 握手与时钟域

- 命令路径（video_clk → dri_clk）：`ov5640_reg` 锁存 `{rw,addr,wdata}` 并翻转
  `pt_req_toggle`；`ov5640.v` 内用 `dri_clk` 打两拍 + 边沿检测得到单拍 `pt_req_pulse`。
  数据在 toggle 前已稳定，属“数据 + toggle”CDC。
- 结果路径（dri_clk → video_clk）：`ov5640.v` 在 `i2c_done && pt_busy` 时锁存
  `i2c_data_r`/`i2c_ack` 并翻转 `pt_done_toggle`；`ov5640_top.v` 对
  `pt_done_toggle/pt_rdata/pt_ack` 打两拍回 video_clk；`ov5640_reg.v` 用
  `pt_done_toggle ^ pt_done_d`（**电平变化**，非仅上升沿）锁存结果。
- 仲裁：`i2c_exec = cfg_exec | pt_take`，`i2c_data/i2c_rh_wl` 在 `pt_take` 时选直通，
  否则选配置表。`pt_take = pt_pending & cam_init_done & ~pt_busy`；早到的命令置
  `pt_pending` 挂起，`cam_init_done` 到了自动补发。i2c_dri 的读数 (`i2c_data_r`) 与
  NACK (`i2c_ack`) 都在 `i2c_done` 之前多个周期已稳定（st_data_rd cnt35 / st_stop cnt16）。

### 2.3 地址可达性

- `ovreg_axil_decode.v`：`addr[11:10]==01` → m3（cam3）。0x2000_0500 的 `addr[11:10]=01`，
  读写都进 cam3 寄存器块。
- 交叉开关 `M01_BASE=0x2000_0000, width 29`；PCIe BAR 命中粒度按 4KB 页，0x500 与已验证可读的
  0x400 同页。
- `ov5640_reg.v` 用**全 32 位地址**比较（`raddr_reg`/`s_axi_awaddr` 未掩码），且寄存器均 16 字节
  对齐（规避 PCIe 读忽略 addr[3:0] 的行为）。

### 2.4 顺带修复

`ov5640.v` 内建 ID 诊断锁存原本用 `i2c_rh_wl` 在 `i2c_done` 时判断，但第二笔读 (0x300B)
完成时 `i2c_rh_wl` 在 `init_reg_cnt==2` 已翻 0，导致 ID 低字节永远锁不进。改为在 `i2c_exec`
时锁存 `i2c_was_read <= i2c_rh_wl`，再在 `i2c_done` 用它判断。

## 3. 仿真证据

目录 `sim/cam3_i2c_pt/`（ModelSim 10.6e，脚本 `compile.ps1` / `run_reg_tb.ps1` / `run_pt_fsm.py`）：

1. `compile.ps1`：`ov5640_reg.v` + `ov5640.v` + `ov5640_top.v` 编译 0 error。
2. `run_reg_tb.ps1`（`tb_ov5640_reg_pt.sv`）：直逼真实 `ov5640_reg`——初值、读/写命令字
   拆解 (`pt_rw/pt_addr/pt_wdata`)、done 锁存、写新命令清 done、N/A NACK、toggle 计数，
   全部 PASS。**此测试台抓到并修掉了“只检测上升沿”的真实缺陷。**
3. `run_pt_fsm.py`：按 `// PT_FSM_BEGIN/END` 字节级提取**真实** PT FSM，配伪 I²C 主机——
   未初始化时命令挂起不 exec、初始化后补发、读写方向/地址/数据、NACK 上报、空闲无多余 exec，
   全部 PASS。

## 4. 板端用法

```bash
python3 tools/cam3_i2c_pt.py id              # 读 0x300A/0x300B，期望 0x56/0x40
python3 tools/cam3_i2c_pt.py rd 0x300a       # 读单个传感器寄存器
python3 tools/cam3_i2c_pt.py wr 0x3019 0x02  # 写单个寄存器
python3 tools/cam3_i2c_pt.py flash on|off    # 补光灯: 0x3016/0x301C/0x3019
python3 tools/cam3_i2c_pt.py testpat on|off  # 彩条 0x503D
```

## 5. 遗留局限

- 只对 cam3 可达（cam1/cam2 的 +0x100 落在 prep 窗口）；如需通用化要给每个相机独立页。
- 每笔直通独占 i2c_dri 一次事务，期间内建 FSM 已结束，无并发冲突；但直通不会重试 NACK。
- `i2c_was_read` 修复只改善诊断回读，不改变配置时序。
- 帧控制器的“DMA 补零后仍按普通 done 记账”局限依旧存在（见 `cam3_dma_board_20260926.md`）。

## 6. 文件与备份

改动：`source/ov5640/ov5640/ov5640.v`、`source/ov5640/ov5640_top.v`、
`source/ov5640/ov5640_reg.v`。备份：同名 `.bak_pt_20260926`。
新增：`tools/cam3_i2c_pt.py`、`tools/patch_cam3_i2c_passthrough.py`、`sim/cam3_i2c_pt/`。
