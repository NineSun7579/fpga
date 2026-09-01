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

## Staging dry-run 合同

`scripts/regenerate_bar1_staging.ps1` 的 dry-run 只允许以下两项 IDF 参数变化：

- `BAR1_Enable`: `false` → `true`。
- `BAR1_Size`: `256` → `512`，单位保持 `Bytes`。

`BAR1_MASK_EN=false` 时 `BAR1_MASK` 必须保持 `31'h0`；是否以及如何转换为生成 wrapper 参数，只能由匹配版本的 IP Compiler 决定。脚本不得猜测或手工计算 wrapper mask。

脚本在写入 staging 前要求两个源值各唯一出现一次，并将结果解析为 XML；`check_s2c_bar1.ps1` 随后重新生成 dry-run、验证五个 BAR1 参数、证明除上述两个值外没有其他 IDF 字节变化，并核对 canonical IDF/wrapper 的 SHA-256 未变。损坏 XML、额外参数漂移或 canonical 文件变化均使门禁失败。

## 工具前置条件

2026-09-01 使用 SP6.4 `ip_generate.exe -i` 对 staging IDF 做实际试运行时，工具在生成前报告实例目录缺少 `index.xml`，以非零退出。当前仓库的活动 PCIe IDF 旁确实没有该文件。脚本因此在 `-Execute` 前置检查中明确拒绝继续；需要从同版本 PDS IP Compiler GUI 或完整实例工程导出合法 `index.xml` 后，再重新执行 staging 生成。

2026-09-01 追加审计确认：17 个实时 `origin` 分支、完整 Git 历史、reflog、当前工作区和 PDS SP6.4 安装目录均没有匹配 PCIe `1.2c` 的 `index.xml`。`origin/parallel_driver` 中的 PCIe IDF 与当前活动 IDF 是同一 blob，不能补足实例元数据；安装目录发现的 46 个 `index.xml` 均属于其他 IP。`iplist.xml` 只列出 PCIe `1.4/1.5/1.6`，且对应归档未落盘，因此也不能作为同版本输入。

当前唯一合法入口是取得原始 PCIe `1.2c`、IP ID `042004`、PDS build `146967`、`PG2L50H/FBG484/-6` 的完整实例目录或匹配归档。若无法取得，必须另立“PCIe IP 版本迁移”评审批次，以新版本完整实例为输入并重跑参数、端口、约束、S2-B、S2-C 和后级网表仿真；不得把它描述为原子同版本重生成。

2026-09-01 dry-run 回归曾稳定复现旧脚本把 `BAR1_MASK` 写成 `31'h0(`。修复后，正常 staging 通过 XML/唯一差异门禁；人工损坏 mask 的负向样本被拒绝，缺 `index.xml` 的 `-Execute` 也在调用生成器前非零失败。运行态与负向样本只位于 `build/`，不提交仓库。
