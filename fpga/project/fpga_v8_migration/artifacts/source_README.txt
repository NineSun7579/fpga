YOLOv8n 白板组 A2（V8 / V9）— 三分类 RK3568 INT8
=================================================

目的：在"保留 640 输入、保留 3 尺度（P3/P4/P5）"的前提下，用**减层**（而非减宽）进一步
轻量化 zebra/vehicle/person 三分类模型。依据板端实测（whiteboard_3cls/profiling_20260929）：
- RK3568 是 DDR 带宽受限，`ConvExSwish` 占 67–71%，其耗时基本只随**层数**变化；
- **减宽反而更慢**（V3 w0.20 比 V0 慢 1.8%，Concat/Add/Split 访存变差）；
- 去 P5 最快但伤大目标（large 0.671→0.579）。

因此 A2 只做"减层、不动宽、不动尺度"。本包给出两个候选 V8 / V9。

## 1. 变体定义（相对 V0=stock yolov8n）

| 变体 | 改动 | 层数 | 参数M | GFLOPs | RKNN |
|------|------|------|-------|--------|------|
| V8 | 重复数全降 1 + **去掉 backbone 的 P2/4 C2f**；width 保持 0.25 | 196 | 2.901 | 7.28 | 4.0M |
| V9 | 重复数全降 1 + **轻量 P5**（P5 分支由 C2f1024 改为单个 3×3 Conv1024）；width 保持 0.25 | 184 | 2.841 | 7.61 | 3.9M |

- V8 减少的是最高分辨率的 160×160 阶段（去 P2/4 C2f），压激活且减层。
- V9 减少的是 P5 分支的层（保留 P5 输出，大目标不丢），层数最少。

## 2. 质量（val 1952 图 / 9154 框；mAP50-95）

| 变体 | 整体 mAP50 | 整体 m95 | small(<16) | medium(16-48) | large(>48) | 平衡(HM) |
|------|-----------|----------|-----------|---------------|------------|----------|
| V0 base | 0.8689 | 0.5544 | 0.2741 | 0.4526 | 0.6709 | 0.408 |
| V2 rep1 | 0.8598 | 0.5496 | 0.3510 | 0.4248 | 0.6720 | 0.448 |
| **V8（本包）** | 0.8681 | **0.5496** | 0.3118 | 0.4316 | **0.6816** | 0.429 |
| **V9（本包）** | 0.8624 | **0.5511** | 0.2950 | **0.4554** | 0.6551 | 0.422 |
| V3 w0.20 | 0.8603 | 0.5399 | 0.2781 | 0.4401 | 0.6496 | 0.405 |
| V5 rep1+w0.20 | 0.8571 | 0.5426 | 0.2739 | 0.4398 | 0.6441 | 0.401 |
| V6 rep1+w0.15 | 0.8520 | 0.5326 | 0.2589 | 0.4295 | 0.6579 | 0.389 |
| V7 rep1+w0.20+去P2 | 0.8566 | 0.5444 | 0.2258 | 0.4533 | 0.6617 | 0.368 |
| V1 去P5 | 0.8265 | 0.4914 | 0.2869 | 0.4079 | 0.5791 | 0.391 |
| V4 combo | 0.7997 | 0.4694 | 0.2709 | 0.3692 | 0.5780 | 0.369 |
| REF 预训练 merged_v3 | 0.8590 | 0.5571 | 0.2897 | 0.4509 | 0.6744 | 0.419 |

平衡(HM) = small/medium/large 三桶 mAP50-95 的调和平均。

## 3. 预期速度（板端线性近似，需实测确认）

用报告的经验关系（≈0.057 ms/层，源自 V0 225层 28.83ms 与 V1 155层 24.84ms）：

```
V0 225层 ≈28.8ms    V2 211层 ≈28.0ms    V8 196层 ≈27.2ms    V9 184层 ≈26.5ms
```

即 V8/V9 预计比 V0 快 **~6–8%**，而整体 m95 只差 0.003–0.005，且**3 尺度、大小目标都未明显退化**。
**这只是结构推断，必须以板端 `bench_yolo` 纯 NPU 实测为准。**

## 4. 训练协议（从零，与白板组一致）

```
数据 data/zebra_vehicle_person_merged_v3_balanced (nc=3)
imgsz 640，从零（架构 yaml 随机初始化）
SGD lr0=0.01 momentum0.937 wd5e-4，cos_lr，warmup3，close_mosaic20
epochs 150，patience 40，batch 16，workers 12，cache=False，串行
配置文件：configs/models/wb_v8_w25_nop2c2fn.yaml / wb_v9_w25_lightp5n.yaml
```

## 5. 导出与量化

```
raw-dfl6 导出（clip10）：tools/export_yolov8n_raw_dfl.py --clip 10
RKNN PTQ：tools/onnx_to_rknn.py --quantize int8（asymmetric_quantized-8）
校准：export/calib_zebra640_merged_v3.txt（500 张 merged 训练图）
```

## 6. 输出契约（与现有 3 尺度模型一致）

```
输入：640x640 RGB uint8 NHWC；RKNN 预处理 mean=0 std=255
输出（6 路，顺序固定）：
  box_p3 (1,64,80,80) box_p4 (1,64,40,40) box_p5 (1,64,20,20)
  cls_p3 (1,3,80,80)  cls_p4 (1,3,40,40)  cls_p5 (1,3,20,20)
reg_max=16；strides 8/16/32；锚点 (grid+0.5)*stride
图内无 DFL softmax/投影、无 cls sigmoid、无 NMS；端侧 detview bins=16
```

## 7. 板端验证步骤（照 docs/RK3568_PROFILING.md）

```sh
# 先停 detview/camview，确认 governor=performance，整机空闲
/root/npu/probe_shapes <model.rknn>
/root/npu/probe_quant  <model.rknn>          # 确认全 INT8（type=2），看 box/cls scale
/root/npu/bench_perf   <model.rknn>          # 逐层表：确认 0 FP16 / 0 exDataConvert；看 ConvExSwish 层数
/root/npu/bench_yolo   <model.rknn> 100 1    # 纯 NPU min/mean/max（含输出反量化）
/root/npu/bench_yolo   <model.rknn> 100 0    # 纯 int8 输出
```
重点对比：V8 196 层 / V9 184 层 的 `ConvExSwish` 总时间与纯 NPU 是否真降到 ~27ms / ~26.5ms。

## 8. 选型建议

1. **V9（184 层，本包）**：层数最少、medium 最好、整体 m95 0.5511；轻量 P5 后大目标仍 0.6551。
   预计最快（~26.5ms）。**若板端实测成立，首选。**
2. **V8（196 层，本包）**：small/large 优于 V0，整体 0.5496；medium 偏弱。
3. V2（211 层）平衡度最高（0.448），若板端只小幅提升可保留。
4. 不建议 V3/V5/V6（减宽，板端更慢）；不单独用 V1/V4（去 P5 伤大目标）。

## 9. 文件

```
det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn
det-yolov8n-3cls-wb_v9_w25_lightp5-rk3568-raw-dfl6-int8.rknn
wb_v8_w25_nop2c2f_raw_dfl6_clip10.onnx
wb_v9_w25_lightp5_raw_dfl6_clip10.onnx
README.txt / SHA256SUMS.txt
```
同目录另有完整全变体对照见 `whiteboard_3cls/README.txt` 与 `whiteboard_3cls/profiling_20260929/report.md`。

⚠️ 注意
- V8/V9 与线上 rm8 模型的输出通道不同：本组为 **reg_max=16（box 64 通道）**，线上 rm8 为 32 通道；
  同分辨率下本组输出 IO 略大。若沿用 rm8 的 32 通道可再省一部分输出 IO（下一步可做）。
- 速度收益最终以板端实测为准；本文的 ms 均为层级线性近似。
