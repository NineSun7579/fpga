# main OV5640→PCIe 时钟与复位合同

更新日期：2026-09-04

## 计划时钟域

```text
sys_clk       系统/摄像头配置域，来源待板级确认
cam_pclk      OV5640 源同步采集域
ddr_ui_clk    DDR3 控制器用户域，由 DDR3 IP 产生
pcie_ref_clk  PCIe 差分 100 MHz 参考时钟
pcie_user_clk PCIe DMA/AXIS 用户域，由 PCIe IP 产生
```

## 必须遵守的边界

- `cam_pclk` 数据不能未经 CDC/FIFO 直接进入 `pcie_user_clk`。
- DDR3 写侧和读侧必须分别定义复位释放、帧边界和 FIFO 满/空语义。
- PCIe `ref_clk_p/n` 必须按独立差分 100 MHz 参考时钟审核，不能把板载单端 25 MHz 直接替代。
- 若 `sys_clk` 实际直接来自 25 MHz，必须依据冻结的视频模式重新生成 PLL；不得手工修改厂商生成 IP。
- `ddr_init_done`、PCIe link-up 和摄像头 `cam_init_done` 必须形成明确的启动顺序，不能用 LED 状态替代内部握手。

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

- `sys_clk` 是否为 25 MHz 直接输入或经过外部时钟链。
- OV5640 MCLK 与 `cam_pclk` 的实际频率关系。
- DDR3 IP 用户时钟和参考时钟参数。
- PCIe refclk 实际来源、管脚和 P/N 极性。
- 各复位信号的有效电平、异步断言和同步释放方式。
- PDS 对 `ASYNC_REG`、`set_max_delay -datapath_only` 和 `set_bus_skew` 的最终识别报告与约束优先级。
