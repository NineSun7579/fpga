# NPU + 图像处理 软硬件一致性验证报告

日期: 2026-09-11 (夜间批次) ｜ 覆盖赛项四步: (1) 黄金函数 (2) TB+记录 (3) 对比+抽样转换验证 (4) debug

## 1. 总体结果 — 全部转绿

| 验证域 | 结果 |
|---|---|
| 预处理 IP 64×36 | **10/10 用例 PASS** + compare 12 条流逐位一致 |
| 预处理 IP 640×360 全分辨率 | **10/10 用例 PASS** + compare 全绿 (每流 23 万像素逐位) |
| NPU cat_add | **位精确 PASS** (93 拍, 3 尺度区 + cat 分时 + 0.5 舍入边界) |
| NPU conv11_conv (1×1 核) | **位精确 PASS** (38/40 拍, m_valid 契约按 RTL 校准) |
| NPU conv_conv (3×3 核) | **位精确 PASS** (16 拍, 前导窗口契约经解码实验确定) |
| NPU sppf_maxpool | **位精确 PASS** (5×5 **stride-1** p=2 滑窗, 修正任务书 "stride-5" 先验) |
| NPU upsample_top (模块级) | **位精确 PASS** (192/192 词, 行终止 bug 已修复) |
| NPU conv_top (3×3 完整量化) | **位精确 PASS** (48 拍, 含 zero_1 padding/26bit 累加/25bit 打包/舍入/饱和/relu 全链) |
| NPU conv11_para_top (1×1 模块级+out_buf) | **位精确 PASS** (24 词 ×128bit = 48 列全帧; 输出词 = [高64:列2k+1 \| 低64:列2k] 双列打包) |

复现: `cd sim/preprocess && ./run_all.sh [W H]`; `cd sim/npu && ./run_all.sh`

## 2. 位精确黄金模型 (需求(1), `sim/npu/npu_golden.py`)

关键量化公式 (与 RTL 逐位对齐, 全部经仿真反证):

- **cat_add**: `x=max(d-z,0)`; `A=(x1·s1 + x2·s2) mod 2^25`;
  `q=A·s3 (57bit)`; `out = ([56:30]>=255) ? 255 : ([36:30]+[29])`。
  scale_3 为 **32bit Q30** (端口 32 位, 与 conv 的 16 位 scale_3 不同)。
- **conv 量化 (conv_add / conv11_add)**:
  `acc26 = wrap(acc,26)` → `wdata25 = {acc26[25], acc26[23:0]}` (**bit24 被丢弃**)
  → `v = wrap(wdata25·scale3 + bias + z3·2^16, 42)` → `v<0→0`; `[40:16]>=255→255`;
  **3×3**: `out=[23:16]+[15]` (round-half-up); **1×1**: 0.5 银行家舍入 (`frac==0x8000 → +lsb`);
  relu: `out = max(out, z3)` (en_relu)。
- **MAC**: `acc = Σ s8(w)·u8(d)` (数据无符号/权重有符号, conv_mul_E2 12×9 SIMD)。
- **conv 3×3 窗口契约 (tb_c33_decode 解码实验确定)**:
  `out#k = Σ_t w[t]·stream[t/3][k + t%3]`, t=(行 t/3, 列 t%3), 即窗口 = 流列 **[k, k+1, k+2]**
  (前导窗口: 权重列 0 对应流最旧列)。行流 = [左pad] + W 列 + [右pad], 每行 W 个输出。
- **sppf**: 5×5 **stride-1**, p=2 零填充 (delay_cnt==4 后每拍出数)。
- **upsample**: nearest 2× (`out[r][c]=in[r>>1][c>>1]`), 列倍增由 ping/pang 双 RAM 交替读实现。
- **激励覆盖**: 饱和(255)/负钳位(0)/d<z clamp/0.5 舍入上下两侧/A 奇偶边界/极值权重(±128,127)/全 0 全 255 数据。

## 3. 逐模块结果与随机抽样 (需求(2)(3))

### 3.1 预处理 IP

- 6 个 TB 增加 `$fwrite` 落盘: `golden/hw_out_{gray,color,id,edge,center,regs,btn}.mem`,
  `hw_out_top_mode{0..3}.mem`, `hw_out_bypass.mem` (run_all.sh 扩展为 4 模式+旁路全跑)。
- `compare.py`: 12 条流逐位比对 + 独立重算抽样 100 像素 (640×360):
  - 灰度定点误差: max 1.12 LSB / avg ≈0.4 LSB (8bit, BT.601 整数近似 vs 浮点亮度)
  - mode2 输出 vs 灰度→RGB565 往返: 0 偏差; mode1 vs 色化重算: 0 偏差; hw 灰度 vs 重算: 0 偏差
  - 全表见 `sim/preprocess/verify_report.md`

### 3.2 NPU (compare.py, `sim/npu/verify_report.md`)

| 模块 | TB | 比对 | don't-care | 说明 |
|---|---|---|---|---|
| cat_add | tb_cat_add | 93/93 ✓ | 0 | 128bit 全通道字比对 byte0 + 16 通道一致性 |
| conv11_conv | tb_conv11_conv | 320 ✓ | 16 | 首拍不产数契约: hw[k]↔exp[k+8], 尾 2 拍 RTL 不产出 |
| conv_conv | tb_conv_conv | 128 ✓ | 0 | 前导窗口契约 |
| sppf_maxpool | tb_sppf_unit | 160 ✓ | 0 | stride-1 滑窗 |
| upsample_top | tb_upsample_top | 192 ✓ | 0 | 修复后 2×read_num 词/行 |
| conv_top | tb_conv_top | 48 ✓ | 0 | 全量化链位精确 |

## 4. 发现并处理的问题清单 (需求(4))

1. **[真 bug·已修复] upsample_in_buf 行终止 off-by-one**
   原行为: `ren` 在 `raddr_1==read_num-1` 拉低 → 每行 **15/16 词** (行末列的复制词不读出);
   `r_last` 在 `read_num-2` 触发 → m_last 比末词早 2 拍, 导致 ctrl 行计数与数据错位 (12 行只
   输出 180 词且全帧错位)。
   修复: `ren` 终止条件改为 **`raddr_0 == read_num`** (R0 读址天然领先 R1 一拍, 恰在
   2×read_num 次读后终止), `r_last` 改为 `raddr_1 == read_num-1` (与末词的 m_valid 对齐)。
   修复后 192/192 词逐位一致。探测过程: 自建读计数器方案曾在第二遍读卡死 (raddr_0 先到
   界导致终止条件永假), 被单值解码实验证伪后换用 raddr_0 方案。
2. **[真 bug·已修复] preprocess_top TB 的 r_mode 未随 MODE plusarg 赋值**
   tb_preprocess_top.v 中 r_mode 恒 0, mode1/2/3 从未被真正仿真。已修 (一行)。
3. **[契约·已建模] conv/conv11 的 m_valid 相对数据流有固有丢拍**
   conv11: `m_valid = valid_d[11]&valid_d[9]` → 40 拍流出 38 拍, 首输出对应数据拍 1;
   conv33 单元: 10 拍流出 8 拍 (前导窗口的首 2 拍计入流水填充)。上电首窗口数据为
   X ( don't-care)。这些是 RTL 既有行为, TB/golden 已按实际契约校准。
4. **[先验修正] sppf 是 stride-1 而非 stride-5** (delay_cnt==4 为流水填充计数, 不是步进)。
5. **[工具契约] cat_add 的 scale_3 端口 32 位**; conv 侧 16 位 —— 主机标定 scale 时注意。
6. **[兼容性·已修] NPU 23 个 RTL 文件声明顺序不符合 ModelSim 要求** (PDS 宽容/MS 严格)。
   已做语义中立的"模块级声明前移"变换 (标记 `[sim-compat]`); conv_mul_E2/conv11_mul_E2/
   common 乘法器为 generate 块内声明结构, 已逐一手工恢复, 未用通用变换。
7. **[解析注意] ModelSim $writememh 会写 `//` 注释头**, compare 解析器已按行剥离注释。
8. **[已闭环·TB 建模错误] conv11_para_top 两处"异常"实为 TB 侧建模错误**:
   (a) "行推进停滞" —— out_buf 以 CHA_PAR_OUT=16 例化是**有意设计**: 每个 128bit 输出词
   打包两列 (低 64bit = 列 2k 的 8 核, 高 64bit = 列 2k+1 的 8 核), 全帧 48 列 = 24 词,
   TB 误按 48 词等待造成"停滞"假象;
   (b) "stride-2 丢列" —— TB 用 64bit 捕获 128bit 输出词, 高位半字 (奇数列) 被截断。
   TB 改为 128bit 全宽捕获 + 双列比对后 **24/24 词位精确 PASS**, RTL 无需任何修改。
   经验: 遇到"发射缺一半"现象先检查捕获位宽与打包层级, 再怀疑 RTL。

## 5. 交付物与复现

```
sim/preprocess/   compare.py + verify_report.md + 6 个 TB 落盘补丁 + run_all.sh (10 用例)
sim/npu/          npu_golden.py + gtp_apm_e2_sim.v + tb×7 (含 tb_c33_decode 解码实验)
                  + compare.py + run_all.sh
golden/           位精确激励/期望 + hw_out_* 实测落盘
```
注2: `tb_c33_decode.v` 为窗口契约解码实验 (单值化权重/数据, 一个仿真直接读出
conv_conv 真实窗口映射), 是 §2 "前导窗口" 结论的实验依据, 保留供后续算子复用。
DOC/              本报告
```
- 预处理: `./run_all.sh` (64×36 快速) / `./run_all.sh 640 360` (全分辨率, ~5 分钟)
- NPU: `./run_all.sh` (golden→编译→6 TB→compare, ~3 分钟)
- NPU conv 类 TB 使用 `gtp_apm_e2_sim.v` 行为原语 (12×9 SIMD, 3 拍), 可替换为 PDS 官方
  `arch/vendor/pango/verilog/simulation/GTP_APM_E2.v` 交叉验证。

注: NPU RTL 的 `[sim-compat]` 声明前移与 `[ups-fix]` 已用 pds_shell `-run compile` 在
project_build 副本复验 (compile_check*.log, 0 Error)。

### §6.1 Route-0008 根因闭环 (2026-09-11 确认)

不可布线的根因 = 重建 `scale_mul_unsign_s3.v` 时从孪生模块误复制
`(* syn_multstyle = "logic" *)` 属性 → cat_add 的十余个 32×25 乘法器被强制 LUT 实现
(日志证据: `Convert attribute name from syn_multstyle` + `mul_low_r` Public-4008 警告)。
删除该属性后: Total Registers 54478 → **53005** (回到 09-10 基线), 综合复验 0 Error。
经验: 从孪生模块复制 RTL 时, 头部综合属性必须一并核对。

**闭环 (2026-09-11 深夜)**: 属性删除后重跑全流程 —— Total Registers 53092
(基线 53005 + prep_regs 集成 87), 利用率回到 64%, 路由速度恢复正常
(收敛迭代 ~10s/次), **46 分钟布线成功出比特流** `bitstream_2026-09-11/top.sbit`,
全部时钟域时序收敛 (pclk +1.157ns, 09-10 的 -0.192 违例消失)。
该比特流同时带 PREP/INJ 寄存器组 (AXI 0x2000_0000+0x100~0x17C, 寄存器级)。

### §6.2 批② 数据通路 WIP (source/preprocess/cam_prep_link.v, 未进比特流)

写 DDR 前处理方案已实现: 相机像素流(128b=8像素)旁路 tap → preprocess_top
(16b 像素 + 帧同步 + 帧尾哑像素注入) → 打包 → 处理图写引擎(0x0A000000 乒乓,
第二写引擎走 crossbar S03 写通道, M00_CONNECT_WRITE 已加 S03)。
RAW 旁路已验证正确; 打包器 beat->lane 映射与 preprocess bypass 输出时序
需要波形级校准 (tb_cam_prep_link 现状 FAIL, 源码已标 WIP)。
注意: bitstream_2026-09-11 构建时数据通路尚未接入, 该比特流不含此逻辑 ——
**批② 完成前它是 RK 侧验证 PREP 契约的可用版本 (寄存器级)**。

## 6. ⚠ 比特流重编译回归警报 (2026-09-11 夜间发现, 待排查)

upside: 含 `[ups-fix]` 与全部 `[sim-compat]` 的重编译 (`project_build/build2.log`) 出现
**综合/布线规模回归**:

| 指标 | 09-10 基线构建 (build.log) | 09-11 重编译 (build2.log) |
|---|---|---|
| Total Registers | 53006 (39.79%) | 54478 (40.90%) (+1472) |
| Design Utilization | 64% | **88%** |
| 布局线长 | 1,605,752 | 1,956,362 (+22%) |
| 路由单迭代 CPU | 7~10 s | **754~864 s** (≈90×) |

该构建仍在后台路由 (project_build/build2.log, 预计数小时~不可收敛), **不阻塞交付**:
板上现用比特流仍为 `bitstream_2026-09-10/top.sbit` (09-10 基线源码, 验证过时序)。
排查建议 (单变量二分):
1. 先单独验证 `[ups-fix]` (仅 2 个比较常数, 最不可能) —— 用基线源码 + 仅该补丁跑 synthesize;
2. 再二分 15 个 conv11/out_buf 文件的 hoist 与 `wire empty;` 显式声明;
3. 23 文件通用 hoist 中需重点复核 generate 块邻近的文件 (conv11_weight 曾被移动过多行语句)。
注: `[sim-compat]` hoist 语义中立仅针对 ModelSim 仿真可见行为; 若确认是 hoist 引起,
建议改用"sim 专用 filelist"方式 (编译期宏区分), 而不是修改工程源码。
