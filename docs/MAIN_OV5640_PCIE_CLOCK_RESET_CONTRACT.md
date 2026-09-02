# main OV5640→PCIe 时钟与复位合同

更新日期：2026-09-02

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

## 当前待确认

- `sys_clk` 是否为 25 MHz 直接输入或经过外部时钟链。
- OV5640 MCLK 与 `cam_pclk` 的实际频率关系。
- DDR3 IP 用户时钟和参考时钟参数。
- PCIe refclk 实际来源、管脚和 P/N 极性。
- 各复位信号的有效电平、异步断言和同步释放方式。
