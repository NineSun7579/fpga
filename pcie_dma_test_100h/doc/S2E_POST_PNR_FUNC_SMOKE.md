# PCIe S2-E PNR 后功能受限 smoke 契约

## 状态与范围

S2-E 的可复现 Questa 工程已归档，PDS 功能网表生成、静态合同和动态 Questa
受限 smoke 均已完成。

本 smoke 只验证：

- PG2L50H PNR 功能网表能够结合 Logos2 USIM/VSIM 与 PCIe/HSST 厂商模型编译和展开；
- 项目 `button_rst_n`、`perst_n` debounce/sync 路径可释放和重新断言；
- 强制控制保留的 link 观察网络后，reference-clock LED counter 路径仍可运行；
- PERST# 重新断言可复位该计数路径，而 button reset 不错误接管其复位所有权。

它不证明 PCIe LTSSM/link、DMA、SDF 标注、时序、RK3568 实板或发布通过。

## 工程归档

版本库只保留项目内的可复现工程定义：

```text
sim/questa/
├─ post_pnr_func.f
├─ run_post_pnr_func.do
└─ tb/
   └─ tb_pcie_dma_post_pnr_func.sv
```

`work`、`modelsim.ini`、transcript、日志、波形、PDS 数据库和网表只写入
`build/`，不进入 Git。Questa 安装和许可证配置始终是仓库外输入。

## PDS 双进程网表合同

PDS `2022.2-SP6.4` 在同一 shell 中只允许执行一次 `gen_netlist` action。因此完整
构建采用两个隔离进程：

1. canonical `build/pds/` 生成 timing netlist、slow-corner SDF 和 bitstream；
2. 将该 PDS 工程复制到同目录深度的 run-scoped 工作目录，在副本中启用
   `func_sim_only`、禁用 `sdf_annotate`，再生成独立功能网表；
3. 校验功能网表非空且不含 `$sdf_annotate`，归档为
   `build/pds/generate_netlist/pcie_dma_test_func.v`；
4. provenance 同时绑定功能网表、功能网表生成日志和原有七项最终证据。

当前 PDS run `9952da4164f040d5924a558baa5cd8ca` 的 manifest 为
`complete/valid`，包含 43 项 canonical 输入和 9 项最终证据。功能网表为
11,132,812 bytes，不含 `$sdf_annotate`。baseline gate 返回 0，strict gate 仍因
H2-B1 的五类已知板级阻断返回 1。

## Questa 合同

DO 文件逐行扫描功能网表，避免把完整网表回显到 transcript；只抑制已审核的厂商
`V_DRM18K_E1` 重复 `vopt-2697` warning，其他 warning/error 保持可见。动态成功必须：

- 日志包含与启动器相同且唯一的 `SIM_RUN_ID`；
- 唯一输出 `INFO: POST_PNR_FUNC_RESET_PATH_OK`；
- 唯一输出 `TEST PASS`；
- Questa 与 PowerShell 均返回 0。

Questa `2021.1` run `927abae8ed7d40aeb5d6f706b3723e0a` 使用当前功能网表运行至
`491965 ns`，日志包含唯一 run marker、唯一 `INFO: POST_PNR_FUNC_RESET_PATH_OK`
和唯一 `TEST PASS`；`Errors: 0, Warnings: 1, Suppressed Warnings: 80`，PowerShell
退出 0。唯一未抑制 warning 来自厂商 HSST 受保护模型，不属于项目 RTL 告警。

## 执行

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_post_pnr_func_sim.ps1

powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action sim-post-pnr-func `
  -QuestaBin '<Questa-win64-directory>'
```

PNR 后时序/SDF 仿真属于下一独立批次，不得由本 smoke 代替。
