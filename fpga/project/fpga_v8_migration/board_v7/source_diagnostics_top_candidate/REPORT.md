# V7 四路源帧诊断顶层候选报告

结论：隔离候选的完整顶层 elaboration、实际 crossbar 寄存器事务、四路完整源帧、
lease/previous 字段和复位合同回归通过。尚未运行 PDS、综合、布局布线或上板，
不能将此结论视为物理签核或完整 RAW/DDR/PCIe 数据流验收。

## 交付与改动

- 入口 `v7_sdt_top.v`，完整登记源见 `sources.json`；接线说明见 `INTEGRATION.md`。
- `generate.py` 采用字节替换、精确匹配次数断言及冻结输入 hash；四个派生 RTL
  都有对应 `.diff`，`generation_operations.json` 记录替换内容与匹配数。
- 新窗口精确为 `0x20001000..0x200013ff`；真实 S00→M01→原 bridge→新增 bus
  →原 decoder。M01 是 29-bit 窗口 `0x20000000..0x3fffffff`，未改地址表。
- binding 导出实际 capture 输入、原 negedge 输出和 `!ov_rst_n | !cam_rst_n`。
  CAM3/4 保留64拍 VSYNC 资格化；诊断观察资格化后的 capture 输入。
- RAW、6cam、motion、COOP/CAPL 的原模块和数据路径保留；未引入 `cdc_boundary*`。
  本次测试只验证其相关地址路径及完整实例加载，不声称重新验收全部数据流。

集成中发现并在本目录修正三项问题，冻结输入与原诊断候选均不修改：

1. 原诊断 bus 下游先 AW 后 W，与真实 `ov5640_reg` 等待 AWVALID 和 WVALID
   同时有效的逻辑死锁。`v7_sdt_bus` 收齐请求后同时提交 AW/W，分别记录握手。
2. 冻结顶层退役的 M00 写返回输入悬空，导致有效的 M01 B 响应无法通过返回仲裁。
   本地 top 将 M00 BID/BRESP/BUSER/BVALID 明确接0；独立写仲裁及 M00 读路径不改。
3. PCIe 4-bit LEN 接到 crossbar 8-bit 输入，完整仿真观察到 M02 ARLEN=z0，
   COOP 合法访问报错。本地 top 显式零扩展 S00 AWLEN/ARLEN。

未发现需要修改 `v7_sfd_candidate` 源帧字段逻辑的问题；全部字段断言已实际执行。

## 验证证据

| 检查 | 实测结果 | 日志 |
|---|---|---|
| 完整硬件候选编译 | 0 errors / 0 warnings | `compile.log` |
| 完整顶层加载 | `TOP_ELAB_PASS`，932 个实际实例 | `elaboration.log`, `hierarchy.txt` |
| 顶层事务与完整帧 | `SDT_ALL_PASS checks=14540` | `top_simulation.log` |
| 实际 M01 访问 | 1234 reads / 214 writes；17 次旧 decoder 读 | 同上 |
| 原 bus 合同回归 | `SDB_ALL_PASS checks=11986` | `unit_regression/tb_v7_sdb.log` |
| 修正 bus 同套合同回归 | `SDB_ALL_PASS checks=11986` | `unit_regression/corrected_bus.log` |
| 原源帧回归 | `SFD_DONE checks=2038 errors=0`、`SFD_ALL_PASS` | `source_regression.log` |
| 模块/输入审计 | 无新增模块重名；190 项源 hash、1200 项编译输入 hash 一致 | `audit.json` |
| 物理对象存在性 | 68 个实际信号对象通过断言 | `physical_hierarchy.csv/json` |

四路同时驱动真实顶层 DVP，经真实 binding/capture/negedge 后读取每路全部16个字段。
没有 force 源帧计数器或快照。

| 相机 | 字节 | HREF 段 | 奇数段 | aligned / native valid | word7 |
|---|---:|---:|---:|---:|---|
| CAM1 | 614400 | 480 | 0 | 307200 / 307200 | `00050015` |
| CAM2 | 614400 | 481 | 2 | 307199 / 307199 | `00050015` |
| CAM3 | 614400 | 482 | 4 | 307198 / 307198 | `00050055` |
| CAM4 | 614400 | 487 | 14 | 307193 / 307193 | `00050055` |

后两路 word7 的 gap 多64拍，符合其实际 VSYNC 资格化延迟。
持有 lease 时再输入帧，64个字段全部保持；释放后新 lease 的64字段逐项匹配，
seq=3、bytes=20、valid=10，previous bytes=16、previous valid=8，
previous 指向紧邻的丢弃帧。新 word7 为 CAM1/2=`00070006`、CAM3/4=`00070046`。

地址测试包含四路旧 CAM enable 写/读/恢复、PREP、motion magic、COOP/CAPL magic，
窗口每路全部非法读偏移，以及窗口外 `0x20001400/0x20000ff0/0x30001030` 的原路由。
顶层总线刺激位于 DMA 输出，故非法非对齐地址测试不代表真实 PCIe DMA 会保留低4位。
原 bus 回归补充非法写、字节 strobe、AW/W 顺序和跨字段读取期间 reset 检出等合同。
epoch 饱和 fail-closed 是 RTL 规则，本次没有运行到32位饱和点。

复位测试实际运行65536拍 camera_ctrl 启动计数；2ns camera reset 脉冲触发一次 epoch，
保持已经承诺且受背压的 R/B，结果承诺前 reset 返回 SLVERR，其他相机 lease 保持。
整个 AXI reset 清接口与 lease，camera_ctrl 不重启。

## 仿真与物理边界

使用 PDS 官方 primitive、加密 ModelSim 模型及冻结 DDR 官方 sim_lib，无 IP 空壳。
`sim_views/` 的声明整理仅用于兼容 ModelSim，差异和规则见 `sim_order.py`。
事务 TB 提供 AXI/控制时钟、DDR init 和 I2C 完成；free_clk 停止，避免启动 PHY。
不验证 PCIe 训练、DDR 校准或完整帧写入 DDR。

完整 elaboration 为600 warnings：303 个缺端口连接、119 个连接数不足、
177 个位宽不匹配、1 个 novopt 提示。事务仿真为298 warnings。
`warnings.json` 保存逐项消息与类别；主要来自冻结连接、未驱动的 elaboration TB
以及厂商模型。没有把它们统一判作无害；通过的数字回归不能替代综合位宽和连接审查。

`PHYSICAL_REVIEW.md` 和68对象清单覆盖 reset 同步链、request/ack/status 同步链、
512-bit mailbox→host_bank、源对齐寄存器及8个真实 binding negedge 发射寄存器。
综合后必须重新解析 cell/pin，评审 bundled-data max_delay、例外优先级、半周期路径、
复位最小脉宽及 recovery/removal；目前无 Fmax/面积/亚稳态签核。

## 复现

在工作区根目录运行：

```text
python project/fpga_v8_migration/board_v7/source_diagnostics_top_candidate/verify.py
```

依次执行生成/完整编译加载、顶层和源帧回归、两套原回归及修正 bus 回归、审计、
物理对象存在性验证。`test.py` 会检查编译输入 hash，防止用旧库验证已变化 RTL。
`compiled_hashes.json` 包含实际 RTL/IP/vendor 输入，`verification.json` 封存交付证据 hash。
全流程只写本候选目录；没有修改生产/冻结/IP，没有启动 PDS、远程操作或烧写。
