# GitHub PR 静态门禁

更新日期：2026-09-02

仓库通过 [`.github/workflows/repository-gates.yml`](../.github/workflows/repository-gates.yml)
在 pull request、`main` push 和手动触发时运行仓库级静态门禁。工作流使用
Windows runner 与 `pwsh`，执行：

```powershell
./scripts/check_repo_consistency.ps1
```

## 安全边界

- workflow 权限只有 `contents: read`；
- checkout action 固定到已审核的完整提交 SHA，并关闭凭据持久化；
- `fetch-depth: 0` 为敏感差异门禁提供 merge-base 所需历史；
- workflow 不读取 GitHub secrets，不配置或打印 PDS/Questa 许可证；
- PDS、Questa、STA、SDF、位流和实板验证仍由具备工具及许可证的受控本机执行。

因此 `Static repository gates` 通过只表示当前静态合同、清单、脚本 AST、仿真归档
边界和敏感信息门禁通过，不表示三个活动项目已经完成实现或四级仿真。

## GitHub 设置

workflow 首次成功运行后，可在目标分支的 ruleset 或 branch protection 中把
`Static repository gates` 设为 required status check，并启用：

- 合并前必须通过 pull request；
- required check 必须成功；
- 禁止 force push；
- 禁止删除受保护分支。

这些设置只约束协作流程，不替代 owner 对板卡型号、原理图/BOM、IP、约束和发布
证据的审核。
