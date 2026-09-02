# 测试覆盖与证据缺口

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual refresh from TODO and simulation matrix

| 项目 | 当前覆盖 | 主要缺口 |
|---|---|---|
| DDR3 | 厂商示例和 PDS 历史构建 | 项目级 BIST、TB、四级 Questa、板级闭环 |
| PCIe | S2-A/S2-B/S2-C/S2-D/S2-E 项目内归档；S2-F 受时序模型阻断 | PG2L100H IP、真实 DMA 闭环、SDF 时序签核 |
| 双 OV5640 HDMI | C0 参考审计、C1-A 文档骨架 | 产品 RTL/IP/FDC、集成 TB、四级 Questa、实板验证 |

静态门禁只检查文件、路径、文档和退出契约，不宣称动态实现或硬件通过。
