# M3-A：PG2L100H 四 IP 当前版本核验审计

状态：当前平台审计；旧 PG2L50H 迁移方案已作废。更新日期：2026-09-04。

当前平台固定为：

```text
RK3568_MES2L100H（FPGA + ARM）
PG2L100H-6IFBG484
Logos2 / PG2L100H / FBG484 / -6
```

## 1. 结论

`ddr3_ip`、`pll_clk`、`rd_fifo` 和 `wr_fifo` 的活动 IDF 均面向 PG2L100H，但由较早的 PDS SP4.2 生成。当前工程不能仅凭文件名或历史七阶段产物判断它们满足 SP6.4、当前板级参数和产品顶层要求。

M3-A 的当前任务是：在不改写 canonical 目录的前提下，核验活动 IP 的目标、版本、端口、隐藏派生参数、仿真资产和约束边界；若版本或参数不一致，则使用 PDS 2022.2-SP6.4 在 PG2L100H 目标下建立独立 staging，再经审核后决定是否升格。

旧 PG2L50H 迁移文档、seed、staging 和构建结果全部属于历史错误假设，不得执行、复制或作为当前输入。

## 2. 范围与禁止项

M3-A 只做证据审计和 staging 规划，不直接修改：

```text
41_ov7725_hdmi/prj/ipcore/**
41_ov7725_hdmi/prj/ip_backup/**
41_ov7725_hdmi/rtl/**
41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc
```

禁止手改 IDF 的 `<version>`、`<device>` 或隐藏参数；禁止手改厂商生成 Verilog；禁止以旧 STA、网表、SDF、位流或失败指纹替代当前 100H 证据。

## 3. 当前资产事实

| 实例 | 当前观察 | 当前处理 |
|---|---|---|
| `ddr3_ip` | IDF 目标为 PG2L100H，版本来自旧批次 | 用 SP6.4 核验目标、参数、wrapper、FDC/RCF 和仿真文件表 |
| `pll_clk` | IDF 目标为 PG2L100H，版本来自旧批次 | 核验输出频率、相位、占空比、lock 语义和 clock object |
| `rd_fifo` | IDF 目标为 PG2L100H，版本来自旧批次 | 核验宽度、深度、时钟、复位、资源模式和模型 |
| `wr_fifo` | IDF 目标为 PG2L100H，版本来自旧批次 | 核验宽度、深度、时钟、复位、资源模式和模型 |

历史 `prj/impl.tcl` 含绝对路径和旧 GUI 操作，只能作为事实记录；当前可重复入口仍是 `scripts/build.tcl` 和 `scripts/run.ps1`。

## 4. 必核对的业务参数

### DDR3

- 颗粒料号、数量、容量、rank、x16/x32 组织；
- row/column/bank、DQ/DQS/DM 宽度和 `mem_a` 地址位宽；
- 目标速率、参考时钟、初始化/校准输出；
- wrapper 端口、用户口握手、地址单位和 `I_ips_ddr_top` 层级；
- FDC/RCF 的管脚、电气标准、时钟对象和实际对象命中。

当前已知缺口是手写顶层/FDC 与活动 IP 的 `mem_a` 位宽存在差异，不能用消除 warning 代替板级判断。

### PLL

- `sys_clk` 输入频率和容差；
- `pixel_clk`、`pixel_clk_5x`、DDR reference clock 的频率、相位和占空比；
- `lock` 输出极性、释放时序和 generated-clock 唯一性；
- 当前 PG2L100H 资源和 PDS clock object 是否匹配。

### FIFO

- 读写宽度、深度、混宽比例和数据顺序；
- 异步复位/flush 语义、almost-full/empty 阈值；
- DRM 资源模式和数量；
- 仿真模型、filelist、wrapper 端口和层级是否漂移。

## 5. 当前 staging 规则

1. 使用 PDS 2022.2-SP6.4。
2. 目标固定选择 `Logos2 / PG2L100H / FBG484 / -6`。
3. 四个实例分别输出到：

```text
41_ov7725_hdmi/build/ipgen/pg2l100h/ddr3_ip
41_ov7725_hdmi/build/ipgen/pg2l100h/pll_clk
41_ov7725_hdmi/build/ipgen/pg2l100h/rd_fifo
41_ov7725_hdmi/build/ipgen/pg2l100h/wr_fifo
```

4. 保存参数记录、IDF、wrapper、FDC/RCF、仿真文件表和完整生成日志。
5. 生成前后校验 canonical IDF SHA-256 不变。
6. 对目录级差异执行人工审核，不得只比较 IDF header。

## 6. 升格条件

只有以下条件全部满足，才允许把 staging 资产升格到 `prj/ipcore/**`：

1. 板级原理图/BOM 已关闭 DDR3 组织、管脚、电压、时钟和复位；
2. 四个 IP 均明确为 PG2L100H、当前 PDS 版本和当前参数；
3. wrapper 端口、用户口握手、层级和仿真资产与手写顶层一致；
4. FDC/RCF、clock object、I/O 电气属性和资源位置有可追溯依据；
5. 从空 `build/` 完成 compile、synthesize、dev_map、PNR、STA、SDF、网表和位流；
6. 严格 gate、项目级 Questa 仿真和 Nexus/文档记录同步通过。

任一条件未满足时，M3 保持阻断。旧 50H 迁移记录只保留在 Git 历史和明确的历史证据位置。
