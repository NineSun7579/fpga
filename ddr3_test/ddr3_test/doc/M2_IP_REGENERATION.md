# M2：PG2L100H DDR3 IP 版本核验与重生成边界

状态：当前平台审计；旧 PG2L50H 重生成脚本和结果已作废。更新日期：2026-09-04。

## 1. 目标

当前工程目标为 `RK3568_MES2L100H / PG2L100H-6IFBG484`，PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。

本文件只规定如何在不污染 canonical 资产的前提下，核验或重生成匹配当前目标的 DDR3 IP。旧 50H 命令、seed、staging 目录和日志不属于当前执行路径。

## 2. 当前入口状态

仓库中的 `scripts/regenerate_ip.ps1` 是历史 50H 探针，不能执行，也不能作为 PG2L100H 生成入口。当前没有已批准的自动重生成脚本；必须先在 PDS 2022.2-SP6.4 中建立 PG2L100H staging 实例，或者补充经过审核的 100H 自动入口。

任何入口都必须满足：

- staging 目录位于 `build/ipgen/pg2l100h/**`；
- canonical `ip_core/ddr3/**` 在操作前后 SHA-256 不变；
- 目标固定为 `Logos2 / PG2L100H / FBG484 / -6`；
- 生成日志、IDF、wrapper、FDC/RCF 和仿真 filelist 全部留存；
- 禁止手改 `<version>`、`<device>`、隐藏参数或厂商生成 RTL。

## 3. 生成前资料

在启动 IP Compiler 前，必须完成以下板级核对：

1. DDR3 颗粒完整料号、数量、容量、rank 和 x16/x32 组织；
2. row/column/bank、DQ/DQS/DM、byte lane 和 `mem_a` 位宽；
3. 参考时钟、复位、VCCIO、VREF、ODT 和终端网络；
4. 用户口地址单位、写/读握手、初始化完成和返回数据语义；
5. wrapper 层级 `I_ips_ddr_top`、FDC/RCF 管脚与真实 PCB 拓扑。

资料缺失时只做只读审计，不生成、不升格、不更新 canonical 输入。

## 4. 生成后核验

对每个 staging 实例执行目录级差异审计，至少覆盖：

- IDF 目标和生成器版本；
- controller/PHY 端口及隐藏派生参数；
- wrapper 端口方向、宽度、时钟和复位极性；
- FDC/RCF 的管脚、电气标准、时钟对象和资源位置；
- 仿真模型、filelist、层级和日志中的 error/warning；
- 从空 `build/` 完成 compile、synthesize、dev_map、PNR、STA、SDF、网表和位流。

只有上述证据与 PG2L100H 板级资料一致，才允许进入 D3-A 和 canonical 升格评审。
