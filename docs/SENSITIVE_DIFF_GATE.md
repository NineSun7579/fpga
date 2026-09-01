# 许可证敏感差异门禁

更新日期：2026-09-01

## 目标

`scripts/check_sensitive_diff.ps1` 只检查相对 Git 基线新增的文件名和新增行，阻止新的 PDS、Questa 或 FlexNet 许可证配置进入提交。它不读取或打印本机许可证环境变量的实际值。

门禁拒绝：

- `.lic`、`.flexlm`、`.license`、`.flexlmrc` 和 `license.dat` 等许可证文件；
- 包含许可证目录或文件的 Windows、UNC 或 Unix 绝对路径；
- 已知及通用 `*_LICENSE_FILE` 变量的实际赋值；
- 真实 `port@host` 许可证服务器端点；
- FlexNet `SERVER`、`FEATURE`、`INCREMENT`、签名和 host id 等许可证内容。

文档只允许使用 `<license-source>`、`<license-file>`、`<license-path>`、`<port>@<host>`、`${VARIABLE}`、`$env:VARIABLE`、`%VARIABLE%` 或 `$::env(VARIABLE)`。任意其他尖括号内容不能绕过门禁。

## 使用

从仓库根目录执行：

```powershell
.\scripts\check_sensitive_diff.ps1 -BaseRef origin/main
```

运行内置正负向规则自检：

```powershell
.\scripts\check_sensitive_diff.ps1 -SelfTest
```

仓库一致性门禁会自动运行规则自检，并以 `origin/main` 与 `HEAD` 的 merge-base 检查当前提交差异；未跟踪文本文件也会逐行检查。堆叠 PR 可显式传入其真实基线：

```powershell
.\scripts\check_repo_consistency.ps1 `
    -SensitiveDiffBaseRef origin/codex/pcie-s2a-dynamic
```

## 边界

该门禁只阻止新增泄露，不会修改已有文件，也不会清除 Git 历史中的旧路径。历史清理必须作为独立安全批次审核；若需要重写历史和强推，必须先协调所有克隆与开放 PR。
