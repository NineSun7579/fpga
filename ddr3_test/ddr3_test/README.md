# DDR3 bring-up compile 基线

## 当前定位

外层历史工程只引用 DDR3 IP，没有明确产品顶层。本目录的新脚本暂以 IP 自带当前版 `test_ddr` 作为板级 bring-up 顶层，用于建立可重复实现基线；它不是最终产品顶层。

当前配置：

- 器件：`Logos2 / PG2L100H / FBG484 / -6`
- DDR3 IP：Controller + PHY，x16、2 个 DQS、目标 1066 MT/s，当前配置约 1050 MT/s
- 示例顶层：`ip_core/ddr3/example_design/rtl/test_ddr.v`
- 厂商 IP：只通过 `ip_core/ddr3/ddr3.idf` 展开
- 厂商示例约束基线：`ip_core/ddr3/pnr/ddr_test.fdc`
- 优先路由约束：`ip_core/ddr3/pnr/ddr3.rcf`

禁止使用外层旧 `ip_core/ddr_test.fdc`，其中仍包含 PG2L50H 的硬宏位置。

## 构建

快速验证源码、IDF、FDC 和 RCF：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action build
```

执行完整 PDS 流程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action build `
  -RunTo gen_bit_stream
```

生成物统一写入本目录的 `build/`，不提交版本库。

## 已验证基线

已从空 `build/` 执行到 `compile`：

- PDS 退出码为 0，日志没有 `E:`。
- 成功加入 18 个示例 RTL、`ddr3.idf`、FDC 和 RCF。
- 日志共有 272 条 warning；其中 `test_ddr.v:855` 有两条 BIST 错误数据端口位宽不匹配，其余告警按厂商 IP 基线保留并等待完整实现 gate 分类。

该结果只证明源码和约束输入可重复编译，不证明 synthesis、PNR、板级时序、DDR 训练或功能仿真通过。

## 当前阻断项

- 未根据实际板卡核对 DDR3 颗粒、容量、byte lane、VREF、终端、电源和 PCB 拓扑。
- UART RX/TX 没有板级引脚和 I/O 标准约束。
- 当前 testbench 仍连接旧版顶层已经删除的 5 个端口，无法直接 elaboration。
- 当前 BIST 持续随机读写，没有天然有限 `done`；`bist_run_led` 是翻转指示而不是完成信号。
- `test_ddr.v:855` 的 `err_data_pre`、`err_data_aft` 与 BIST 模块端口位宽不一致。
- 行为级、综合后和两个 PNR 后仿真尚未建立可靠的 `$fatal`、超时、`TEST PASS` 和退出码。

在这些信息确认前，不修改 DDR3 IP 参数、FDC、顶层接口或 LED 语义。
