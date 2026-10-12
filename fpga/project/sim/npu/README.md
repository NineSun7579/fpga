# NPU 算子仿真验证 (软硬件一致性, 需求(1)-(4))

## 快速开始

```bash
./run_all.sh     # golden 生成 -> 编译 -> 7 TB -> compare (~3 分钟)
```
依赖: ModelSim (默认 `C:\modeltech64_10.6e\win64`, 可 `MODELSIM_BIN` 覆盖) + Python 3。

## 文件结构

```
npu_golden.py        位精确黄金模型 + 激励/期望生成 (与 RTL 逐位同源)
gtp_apm_e2_sim.v     GTP_APM_E2 行为原语 (12x9 SIMD, 3 拍; 可换 PDS 官方 sim 模型交叉验证)
tb_cat_add.v         cat_add 单元 TB (3 scale 区域 + cat 分时 + 0.5 舍入边界)
tb_conv11_conv.v     1x1 核单元 TB (原始 24bit 累加)
tb_conv_conv.v       3x3 核单元 TB (2 组权重乒乓, 交驱动按真实用法)
tb_sppf_unit.v       sppf_maxpool 单元 TB (5x5 stride-1 p=2)
tb_upsample_top.v    upsample 模块级 TB (nearest 2x)
tb_conv_top.v        conv_top 模块级 TB (3x3 完整量化链)
tb_conv11_para_top.v conv11_para_top 模块级 TB (1x1 + out_buf)
tb_c33_decode.v      窗口契约解码实验 (单值化激励, 一个仿真读出真实窗口映射)
compare.py           hw_out_* vs exp 逐位比对 -> verify_report.md
run_all.sh           一键回归
```

## 已验证的位精确契约 (仿真反证, 与 RTL 同源)

- cat_add: `A=(x1·s1+x2·s2) mod 2^25`; `out = ([56:30]>=255)?255:([36:30]+[29])`;
  **scale_3 端口 32bit Q30**
- conv 量化: acc26→25bit 打包丢 bit24 → ×scale3(16b) + bias + z3<<16 (42b) →
  负 0 / [40:16]>=255 → 255 / 3×3 round-half-up, 1×1 0.5 银行家舍入 / relu=max(q,z3)
- conv 3×3 窗口: **前导窗口** `out#k = Σ_t w[t]·stream[t/3][k+t%3]` (t=行/列),
  行流 = [pad]+W 列+[pad], 每行 W 输出
- sppf: 5×5 **stride-1**, p=2 零填充
- upsample: nearest 2×; 行终止需 `[ups-fix]` (ren 于 raddr_0==read_num, r_last 于
  raddr_1==read_num-1) —— 原始 RTL 每行丢 1 词且 m_last 早 2 拍

## 开放契约 (见 DOC/NPU图像处理一致性验证报告.md §4)

- conv11_para_top: out_buf 行推进停滞 + 16 字节词重排契约
- conv11_conv/conv_conv 的 m_valid 固有丢拍 (已按实际行为建模)

## 注意

- NPU RTL 含 `[sim-compat]` 标记的声明前移 (ModelSim 要求, PDS 已复验编译)
- ModelSim `$writememh` 会写 `//` 注释头, compare 解析器已剥离
- conv 类 TB 编译需 `gtp_apm_e2_sim.v` + common (spram/spram_D/sync_fifo/fifo_ram/pipe)
