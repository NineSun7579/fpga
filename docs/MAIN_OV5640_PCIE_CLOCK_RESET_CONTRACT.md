# main OV5640→PCIe 时钟与复位合同

更新日期：2026-09-04

## 计划时钟域

```text
sys_clk       系统/摄像头配置域，板载 MAIN_CLK_25M 可作为已确认输入候选
cam_pclk      OV5640 源同步采集域
ddr_ui_clk    DDR3 控制器用户域，由 DDR3 IP 产生
pcie_ref_clk  PCIe 差分 100 MHz 参考时钟，板卡手册确认 FPGA F6/E6
pcie_user_clk PCIe DMA/AXIS 用户域，由 PCIe IP 产生
```

## 必须遵守的边界

- `cam_pclk` 数据不能未经 CDC/FIFO 直接进入 `pcie_user_clk`。
- DDR3 写侧和读侧必须分别定义复位释放、帧边界和 FIFO 满/空语义。
- PCIe `ref_clk_p/n` 必须按独立差分 100 MHz 参考时钟审核，不能把板载单端 25 MHz 直接替代。
- 若 `sys_clk` 实际直接来自 25 MHz，必须依据冻结的视频模式重新生成 PLL；不得手工修改厂商生成 IP。
- `ddr_init_done`、PCIe link-up 和摄像头 `cam_init_done` 必须形成明确的启动顺序，不能用 LED 状态替代内部握手。

## 已确认的板级时钟事实

- 板卡手册 v1.1 PDF 第 9 页确认 `MAIN_CLK_25M` 接 FPGA `V4`。
- PDF 第 10 页确认 DDR 参考差分时钟 `GCLK_DDR_133_P/N` 接 FPGA `R4/T4`。
- PDF 第 11 页确认 PI6C557-05BLE 从 25 MHz 产生 100 MHz 差分时钟，同时供 FPGA HSST 与 RK PCIe；
  FPGA `HSSTREFCLK0_CP/CN_QR3` 为 `F6/E6`。
- 以上只关闭时钟源和管脚事实，不关闭 PLL/IP 参数、时钟质量、抖动预算、generated clock 或 STA。

## OV5640 控制与上电时序下限

- OV5640 DVP 指南 2.13 PDF 第 5–6 页确认 `RESETB` 低有效、`PWDN` 高有效。
- 初始保持 `RESETB=0`、`PWDN=1`；DOVDD 应先于或与 AVDD 同时稳定。
- AVDD 稳定至少 5 ms 后才能拉低 PWDN；PWDN 拉低至少 1 ms 后拉高 RESETB；RESETB 拉高
  至少 20 ms 后才能开始 SCCB 初始化。
- 硬件复位低脉冲至少 1 ms。进入 power-down 后 XCLK 至少保持 0.1 ms；唤醒时先恢复 XCLK，
  等待至少 0.1 ms 后再拉低 PWDN。
- 这些是传感器参考下限。真实电源 rail 控制、FPGA Bank 电压、电平转换、XCLK 来源和板级复位树
  尚未冻结，不能直接据此生成产品 FDC/RCF 或启动状态机。

## DDR 到 PCIe 请求 CDC

- 当前项目将 DDR3 `core_clk` 作为 camera MWR32 源域，将 PCIe `pclk_div2` 作为 TX 请求目标域。
- 请求/完成 token 使用三级目标域同步器，online/fault 使用两级同步器；让 peer-offline 比复位导致的
  token 变化早一拍进入事务决策，降低独立同步错拍产生幽灵请求/ACK 的风险。`ASYNC_REG`
  仅是待 PDS 确认的放置提示，不代替 CDC 报告或复位时序证明。
- length/address/data 是需要原子一致性的 bundled-data MCP。源寄存器从请求 token 翻转前同一边沿开始
  保持到完成返回；目标检测同步 token 后再等待一个 `pclk_div2` 周期采样，并在 ACK 前保持本地副本。
- 最终 FDC 必须对源 holding register→目标 capture register 添加明确的 max-delay 和 bus-skew 限制。
  约束值应不大于一个目标时钟周期并留出 setup/uncertainty 余量，精确值由真实 `core_clk/pclk_div2`
  频率和 PDS 时序模型计算。不得对这组 payload 施加整总线 false-path。
- 若顶层使用异步 clock-group，必须验证 PDS 的约束优先级能让上述 datapath-only/max-delay 与 bus-skew
  仍被分析；否则应缩窄 clock-group/false-path，仅豁免同步器第一级 D 路径。
- CDC 签核必须保存：同步器识别、重汇聚、bus-skew/max-delay、unconstrained endpoint 和 waiver 清单。

## mailbox 复位合同

- 每个复位均异步断言、由板级复位树相对本地域同步释放；恢复期间两个时钟必须持续运行。
- local online 在复位后保持低，直到 peer 回应“已观察到低电平”；双方 online 和 token 对齐后才允许请求。
- idle 单域复位可恢复且不得产生幽灵 request/ACK。
- 在途任一域复位：当前事务结果定义为不确定，fault sticky 置位，不自动重放；上层作废当前 frame/slot，
  通过协调双域复位完成 flush。仅靠 volatile toggle 不承诺不丢失、不重复或 PCIe exactly-once。

## 当前待确认

- 产品 `sys_clk` 是否直接使用 FPGA `V4` 的 25 MHz，及其后续 PLL/分频方案。
- OV5640 XCLK 来源、目标频率、容差，以及与 `cam_pclk` 的实际频率关系。
- DDR3 IP 用户时钟和参考时钟参数。
- PCIe refclk 来源和 FPGA 管脚已确认；仍需 P/N 板级极性复核、AC 耦合、PERST#/CLKREQ#/WAKE#
  连接及实际链路时序。
- OV5640 的参考控制极性已确认；仍需 FPGA 具体管脚、Bank 电压、电平转换和产品状态机实现。
- FPGA/RK/DDR3/PCIe 各复位信号的有效电平、异步断言和同步释放方式。
- PDS 对 `ASYNC_REG`、`set_max_delay -datapath_only` 和 `set_bus_skew` 的最终识别报告与约束优先级。
