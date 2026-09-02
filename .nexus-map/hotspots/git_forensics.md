# Git 热点与风险

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual refresh; no new history analysis in cleanup batch

- 高频变更区域：`TODO.md`、`docs/`、`scripts/` 及 PCIe `sim/questa/`。
- 厂商生成 IP、PDS 数据库和仿真运行态属于高风险输入，必须保持边界和来源清单。
- 结构删除仅影响当前树；Git 历史不改写，旧提交仍可通过历史审计查询。
