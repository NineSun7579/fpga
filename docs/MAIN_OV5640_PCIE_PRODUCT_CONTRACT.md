# main 独立 OV5640→PCIe 产品合同

更新日期：2026-09-04

## 当前平台基线

当前平台唯一目标是 `RK3568_MES2L100H`（FPGA + ARM），FPGA 器件为
`PG2L100H-6IFBG484`，PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。
仓库中带有 `PG2L50H` 的历史文件、模块名和仿真脚本不代表当前平台，必须按待迁移行为切片处理。

## 项目边界

本项目在 `codex/main-ov5640-pcie` 分支独立建设，当前基线已重放到 `origin/main`。`parallel_driver` 仅作为只读技术参考，不是本项目的 RTL、IP、约束、构建产物或验收证据来源。

## 首版目标

```text
单路 OV5640
  → RGB565 采集
  → FPGA 图像处理
  → DDR3 帧缓存
  → RGB565/AXI128 打包
  → PCIe DMA Memory Write
  → 主机/RK3568 内存
```

首版只要求完成一帧固定格式图像的端到端传输和主机校验。分辨率、帧率、处理算法、目标地址和帧协议在板级资料闭合后冻结；在此之前不得把历史参考值写入 canonical RTL 或 FDC。

## 首版排除项

- 第二路 OV5640。
- HDMI 输出。
- 动态多帧调度和复杂帧切换。
- 未定义的 RK3568 驱动协议。
- 未经器件和板级资料确认的 PLL、FDC、RCF 或 PCIe IP 修改。

## 验收层级

1. OV5640 SCCB 读 ID、配置完成和 DVP 像素格式正确。
2. 图像处理模块对固定输入产生可预测输出。
3. DDR3 单帧写入/读出数据一致。
4. PCIe DMA 产生正确的 Memory Write，主机收到的数据与参考帧一致。
5. 行为级、综合后、PNR 后功能和 PNR 后时序仿真均具备独立退出契约。
6. `Logos2 / PG2L100H / FBG484 / -6` 目标下完成可重复 PDS 构建、STA 和实板验证。

## 当前事实与阻断

- `main` 当前 PCIe 顶层为 `pcie_dma_test`，只有 PCIe、复位和 LED 端口，没有 OV5640 或 DDR3 产品端口。
- `main` 已有 PCIe DMA 和 128-bit AXIS 内部接口，可作为 PCIe 输出基础，但当前没有本地视频生产者。
- 当前统一器件目标为 `Logos2 / PG2L100H / FBG484 / -6`；历史 PG2L50H 产物和行为证据只能作为待迁移参考，不能作为当前平台验收依据。
- OV5640 模组、DDR3 料号/拓扑、25 MHz 时钟树、PCIe 100 MHz refclk 和主机帧协议仍需一手资料确认。
- 当前已有的 OV5640 DVP→处理→DDR3 记录数组模型→已提交帧读调度→PCIe MWR 请求行为回归，
  均来自旧 50H 假设下的项目自有切片；它们尚未按 100H IP、真实 DDR3/PCIe、物理帧表或 RK3568 主机收帧合同重新核验。
- 进入真实板级连接前必须关闭的资料项见
  [`MAIN_OV5640_PCIE_BOARD_INPUT_CHECKLIST.md`](MAIN_OV5640_PCIE_BOARD_INPUT_CHECKLIST.md)。
