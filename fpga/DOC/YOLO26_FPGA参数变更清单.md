# YOLO26 移植 — FPGA 侧参数变更清单 (任务 1)

训练侧 (RK3568/PC) 定型 YOLO26 层表后, 按本清单逐项同步 FPGA 参数。
**原则: 层表未定型前不动 RTL; 定型后按下表三处同步 + 逐层校验。**

## 1. NPU_LAYER 同步 (三处, 必须一致)

| 文件 | 位置 | 当前值 | 动作 |
|---|---|---|---|
| `source/npu/npu_cdc_top.v` | 例化参数 `.NPU_LAYER(88)` (行337附近) | 88 | 改为新层数 |
| `source/pcie2npu/instruction_buf.v` | `parameter NPU_LAYER = 88` (行6) | 88 | 同步 |
| `source/pcie2npu/npu_ctl.v` | `parameter NPU_LAYER = 88` (行5) | 88 | 同步 |
| `source/pcie2npu/pcie_npu.v` | `parameter NPU_LAYER = 88` (行7, 透传默认值) | 88 | 建议同步 |

新层预估: YOLO26n 去掉 DFL/ending conv 后逐层展开 ≈ 120~140 层。
`LAYER_WIDTH = $clog2(NPU_LAYER+1)` 自动跟随。

## 2. config.v 几何核对 (`source/npu/npu_top/config.v`)

逐层检查新表的最大几何是否超出当前 `define 上限 (GB2312 注释, 注意编码):

| 参数 | 当前值 | 检查内容 |
|---|---|---|
| MAX_IN_COL/MAX_IN_ROW | 640 | 首层输入宽/高 (416 输入时可缩到 416) |
| CHA_IMG_IN / OUT | 512/512 | 最大通道数 |
| CONV33_MAX_IN/OUT_COL | 320 | 3×3 卷积各级特征图 |
| CONV11_MAX_IN/OUT_COL | 160 | 1×1 末端卷积 |
| CAT_ADD_MAX_IN_ROW | 160 | 拼接层 |
| SPPF_MAX_IN_COL | 20 | SPPF 层 |
| UPSAMPLE_MAX_IN_ROW | 40 | 上采样层 |
| WEIGHT_LEN / WEIGHT_SUM | 131072/296960 | 各层权重规模 (按新表最大层) |

**任一超限 → 改 `define 后必须重核 DDR 带宽账 (调优表第二节)。**

> ⚠️ **死宏警告 (2026-09-09 扫描实测)**: config.v 88 个宏中 27 个从未被反引号
> 引用 (全engineering零使用), 改了没有效果: `CONV33_*` 全系列 (CH A_PAR_IN/OUT、
> MAX_IN/OUT_COL/ROW、CHA_IMG_IN/OUT、WEIGHT_*、BIAS_NUM、SCALE_WIDTH、
> MAX_IN/OUT_LEN、MUL_DELAY)、`FOCUS_*` 系列、`CONV11_MAX_IN_COL/ROW`、
> `CONV11_CHA_IMG_IN/OUT`、`CONV11_WEIGHT_*`、`CONV11_BIAS_NUM`、
> `CONV11_SCALE_WIDTH`、`CONV11_MUL_DELAY` 等。真正的几何上限由 npu_top.v
> 例化时透传的宏 (活宏) 与模块内部默认参数共同决定。改宏前先验证:
> `grep -r "\`宏名" source --include="*.v" | grep -v config.v`
> 零命中即为死宏。层表定型后建议清理死宏或改为模块参数透传。

## 3. focus 通路移除 (层表定型后, 真实节省 LUT/BRAM)

YOLO26 输入不再走 focus 切片 (直接 RGB→INT8 3 通道平面):

1. `source/npu/npu_top/npu_top.v` 中 focus 例化与 `source/npu/focus/` 通路断开:
   输入数据直接写 NPU 输入缓存 (3×H×W 平面布局, 见协议 §6)。
2. config.v 中 `FOCUS_*` 参数失效后可注释 (保留文件, 防回退)。
3. 移除后重新可达性分析: `python _attic/reachability_check.py top`
   → `source/npu/focus/` 应整体变为死文件, 登记条目从 project.pds 移除。
4. **量化校验**: PyTorch 量化模型首层输入布局必须与 RTL 一致 (平面非 interleaved)。

## 4. 移植验证 (对照任务 5 标准)

1. **逐层 INT8 零误差**: PyTorch 量化 golden vs FPGA 输出
   (`indata_bin`/`USE_DEBUG` 逐层 dump, CH3 通道回传比对)。
2. **端到端 mAP 差 < 0.5**: 与纯 PyTorch 量化模型在同一验证集对比。
3. 每层 cycle 计数 (找最慢层 → 决定 CONV_CHA_PAR_OUT 提档对象)。

## 5. 训练类别 (RK3568 侧)

红灯 / 绿灯 / 行人 / 车辆 / 斑马线 5 类; 类别表与 NPU 输出的类别索引
写入协议文档附录, FPGA 不感知类别 (只透传结果)。
