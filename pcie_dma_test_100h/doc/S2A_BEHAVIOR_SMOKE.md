# PCIe S2-A 项目级行为 smoke 契约

## 1. 结论

S2-A 使用项目自有 `tb_pcie_dma_test` 实例化真实项目顶层 `pcie_dma_test`，同时用受控的 `pcie_test` 仿真边界替代厂商加密 PCIe IP。该层验证：

- 37 个 canonical HDL 与项目顶层能够按同一源清单进入行为仿真；
- 顶层使用的两个厂商 reset helper 参与真实展开；
- `button_rst_n`、`perst_n`、`core_rst_n`、refclk/pclk 域同步复位的释放和中断行为；
- model-controlled link indication 前后两组 LED 计数器的门控和复位归属；
- 顶层可观察输出不存在未知态；
- 超时和检查失败使用 `$fatal`，成功只输出一次 `TEST PASS`。

S2-A **不验证**真实 LTSSM、TLP、DMA 数据一致性、x2 lane、P/N 极性、100 MHz refclk 电气、PERST# 板级时序或 RK3568 Root Complex。边界模型产生的 `smlh_link_up/rdlh_link_up` 只是测试激励，不能写成“PCIe 链路已建立”。

## 2. 为什么不直接复用厂商 testbench

厂商 `pango_pcie_top_tb.v` 同时实例化 `pango_pcie_top_sim` Root Complex 和 `pango_pcie_top` Endpoint，未实例化项目 `pcie_dma_test`。其 APB/DMA 任务依赖固定的 `u_pango_pcie_top_rc/u_pango_pcie_top_ep` 内部层级，失败只打印文本，且没有全局超时或 `$fatal`。

对应 `pango_pcie_top_sim.do` 还硬编码旧 `D:/pds2022_sp6_4/...` 安装路径，并直接编译 DWC/PCIe/HSST 加密模型。该资产保留为编译顺序、RC 对端和事务序列的 oracle，不修改、不直接作为项目验收入口。

## 3. 文件与职责

| 文件 | 职责 |
|---|---|
| `sim/behav.f` | 以 POSIX 相对路径组合 reset helper、PCIe IP 仿真辅助源、受控模型、37 个 canonical HDL 和项目 TB |
| `tb/pcie_test_smoke_model.sv` | 提供确定性的时钟、复位、idle 协议输出和延迟 link 激励 |
| `tb/tb_pcie_dma_test.sv` | 实例化 `pcie_dma_test` 和固定层级名 `GRS_INST` 的 `GTP_GRS`，执行复位/计数/未知态自检 |
| `scripts/run_behav.do` | 为每个 run id 建立独立 work、映射共享 USIM、记录 run id、编译和运行 |
| `scripts/check_sim.ps1` | 不依赖仿真器的 filelist、端口、TB、DO 和入口契约门禁 |
| `scripts/run.ps1` | 为每次仿真生成唯一 `SIM_RUN_ID`，校验同一日志中的 run marker 和唯一 PASS |

`sim/behav.f` 通过 `-f scripts/pds_sources.f` 复用 PDS 的 37 个 HDL 唯一有序清单，不维护第二份项目 RTL 清单。它只额外加载 `ips2l_pcie_apb_cross_v1_0.v` 这一仿真辅助源；该文件已由 PCIe IDF 管理实现侧资产，不加入 canonical PDS 源清单。filelist 还为 DMA RAM wrapper 的 basename `` `include "ips2l_pcie_dma_ram_init_param.v" `` 显式添加 `+incdir+hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl`。`GTP_DRM18K_E1` 和 `GTP_GRS` 由 Logos2 USIM 解析；Pango RAM 模型固定引用顶层 `GRS_INST.GRSNET`，因此 TB 的全局复位实例名必须保持为 `GRS_INST`。

## 4. 自检时序

1. 差分参考时钟从仿真开始持续运行，`button_rst_n/perst_n` 初始均为低。
2. 检查两枚 LED 的复位值为高。
3. 同时释放两路外部复位，等待两个 `16'hC000` 去抖实例和 refclk/pclk 域同步复位完成；释放早于 49152 个 refclk 周期视为绕过去抖并失败。
4. 在边界模型 link 激励为低时，确认两组 LED 计数器保持 0。
5. 等待模型延迟 link 激励，确认两组计数器开始递增，且顶层 TX/LED 输出没有未知态。
6. 单独断言 `button_rst_n`：pclk LED 域必须复位；refclk LED 计数器必须与负边沿断言前快照完全相等，随后在 link 激励撤销后继续保持。
7. 重新释放 button reset，再单独断言 `perst_n`：两组 LED 域都必须回到复位状态。
8. 在 button reset 保持释放时单独重新释放 `perst_n`，再次执行最小 49152-cycle 检查，证明 PERST# 去抖未被初次联合等待掩盖。
9. 正向路径只打印一次 `TEST PASS`；3 ms watchdog 或任一检查失败调用 `$fatal`。

## 5. 执行与当前状态

静态检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_sim.ps1
```

动态执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action sim-behav `
  -QuestaBin '<Questa-win64-directory>'
```

动态执行前必须满足：

1. `vsim.exe` 可执行且许可证有效；
2. 仓库根公共流程已将 Logos2 USIM 编译到仓库根 `build/simlib/usim`；项目 DO 从 `pcie_dma_test_100h` 目录以 `../build/simlib/usim` 映射该共享库；
3. `GTP_DRM18K_E1`、`GTP_GRS` 能从该库展开。

2026-09-01 使用 Questa Sim-64 `2021.1` 完成动态验证。run id `fab4ccef3e2445abbd9d1cad1e66b2ab` 的 RTL 编译为 `0 errors/0 warnings`，elaboration 成功，仿真运行至 `1476105 ns`，最终为 `Errors: 0, Warnings: 2`，同一 transcript 包含唯一 run marker 和唯一 `TEST PASS`，PowerShell 入口返回 0。

两条 warning 都来自项目 RTL 中 `u_ips2l_pcie_dma` 未连接输出 `o_trgt1_radm_pkt_halt`。该问题作为独立 RTL hygiene TODO 保留；本批不修改 canonical RTL，也不把 S2-A 通过解释为 RTL 零 warning、真实链路或 DMA 通过。

## 6. 后续分层

### S2-B：真实 RC/EP 链路

下一步以厂商 `pango_pcie_top_sim` 作为 RC、项目 `pcie_dma_test` 作为 EP，参数化 PDS 根目录并复用厂商加密模型的原始编译顺序。必须在时限内检查 DUT 的真实 `smlh_link_up/rdlh_link_up` 和 LTSSM 状态；不得用 S2-A 边界模型。

### S2-C：基础 DMA 回读

S2-B 通过后，移植厂商 APB 事务思想到项目真实层级，执行一次地址、长度和数据均固定的 DMA 写读回。数据、完成状态或协议超时均 `$fatal`。UART2APB 继续受 H2-B1 的“公开端口或删除路径”决策约束。

### 后级网表仿真

综合后、PNR 功能和 PNR 时序仿真仍依赖 H2-B1 严格构建闭环、同一次构建 provenance、对应网表/SDF 和真实 DUT 层级。S2-A 的边界模型不得进入这些后级验收。

## 7. 停止条件

- 不把 S2-A 的 model-controlled link 写成真实链路通过；
- 不修改厂商示例、活动 IDF、FDC 或 PDS 产物；
- 缺少 Questa/USIM 时不伪造动态日志或 `TEST PASS`；
- S2-B 未通过前不宣称 DMA、PCIe 协议或板级接口已验证；
- H2-B1 未关闭前，strict build gate 必须继续失败，位流仍不可发布。
