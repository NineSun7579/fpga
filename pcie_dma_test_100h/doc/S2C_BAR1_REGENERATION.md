# S2-C BAR1 重生成审核边界

## 当前事实

- 目标器件：`PG2L50H-6IFBG484`。
- 活动 PCIe IP：`ipcore/pcie_test/pcie_test.idf` 与其生成 wrapper。
- 当前活动配置明确为 `BAR1_Enable=false`、`BAR1_ENABLED=1'b0`、`BAR1_MASK=31'h0`。
- 厂商 Endpoint DMA 示例通过 BAR1 命令窗口写入 DMA 命令和地址；因此当前活动 Endpoint 不能执行该主动 DMA 流。

## 允许的整改方式

1. 使用本机 PDS `2022.2-SP6.4` IP Compiler，在 `Logos2 / PG2L50H / FBG484 / -6` 目标下打开现有 PCIe IP 配置。
2. 启用 BAR1，并使其覆盖命令窗口使用的偏移 `0x110..0x113`；建议至少保留 512 Bytes 地址空间。
3. 将生成的 IDF、wrapper、参数摘要和仿真资产输出到 `build/ipgen/pcie_bar1/` staging 目录。
4. 对比完整参数集、端口、器件元数据、FDC/RCF 依赖和仿真 filelist；审核通过后才允许原子升格到 canonical `ipcore/pcie_test/`。

禁止只手改 `pcie_test.v` 的 `BAR1_ENABLED` 或 `BAR1_MASK`，也禁止只改 IDF 而沿用旧 wrapper。

## 升格前门槛

- BAR1 在 IDF、wrapper、编译数据库和仿真模型中的值一致。
- PCIe S2-B 真实 RC/EP link-up 回归通过。
- S2-C 必须验证完整 canonical 流程：EP MRd 读取 RC BAR0，CplD 写入 EP BAR2，EP MWr 写回 RC BAR0。
- 地址固定为 `0x00000000`，长度为 1 DW，完整数据为 `32'h5432_1000`；地址、BE、completion status、数据和超时均为硬门槛。
- S2-C 成功只能由唯一 `S2C_DMA_WRITE_READBACK_OK` 和唯一 `TEST PASS` 证明。

## 当前结论

本文件只冻结整改边界，不表示 BAR1 已启用，也不表示 S2-C 已通过。当前 `sim/questa/tb/tb_pcie_dma_s2c.sv` 保留为前置诊断入口。

## 工具前置条件

2026-09-01 使用 SP6.4 `ip_generate.exe -i` 对 staging IDF 做实际试运行时，工具在生成前报告实例目录缺少 `index.xml`，以非零退出。当前仓库的活动 PCIe IDF 旁确实没有该文件。脚本因此在 `-Execute` 前置检查中明确拒绝继续；需要从同版本 PDS IP Compiler GUI 或完整实例工程导出合法 `index.xml` 后，再重新执行 staging 生成。
