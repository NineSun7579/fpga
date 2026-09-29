YOLOv8n 白板组（三分类 zebra/vehicle/person）— RK3568 INT8
==========================================================

用途：结构削减对照。三分类数据、**从零训练 150 epoch**，同协议，比较“质量 vs 结构代价”。
全部为 raw-Dfl6 导出 + RKNN PTQ 全 INT8（asymmetric_quantized-8）。

结构代价与质量（val 1952 图 / 9154 框）
--------------------------------------
| 变体 | 削法 | 层数 | 参数(M) | GFLOPs | RKNN | 整体 mAP50/m95 | small | medium | large | 平衡(HM) |
|------|------|------|---------|--------|------|----------------|-------|--------|-------|----------|
| V0 base   | stock yolov8n        | 225 | 3.157 | 8.86 | 4.2M | 0.8689/0.5544 | 0.2741 | 0.4526 | 0.6709 | 0.408 |
| V2 rep1   | C2f 重复全降 1        | 211 | 2.909 | 7.66 | 4.1M | 0.8598/0.5496 | 0.3510 | 0.4248 | 0.6720 | 0.448 |
| V3 w20    | 宽度 0.25->0.20      | 225 | 2.125 | 6.38 | 3.6M | 0.8603/0.5399 | 0.2781 | 0.4401 | 0.6496 | 0.405 |
| V1 noP5   | 去 P5，P3/P4 双尺度   | 155 | 0.970 | 6.30 | 2.0M | 0.8265/0.4914 | 0.2869 | 0.4079 | 0.5791 | 0.391 |
| V4 combo  | 去P5+重复1+宽0.20    | 141 | 0.659 | 4.71 | 1.8M | 0.7997/0.4694 | 0.2709 | 0.3692 | 0.5780 | 0.369 |
| REF 预训练 | merged_v3_ft（对照）  | 225 | 3.157 | 8.86 | —    | 0.8590/0.5571 | 0.2897 | 0.4509 | 0.6744 | 0.419 |

small/medium/large 为各桶 mAP50-95；平衡(HM)=三桶调和平均。

结论
----
- V2（只减 C2f 重复）**几乎零损**（整体 m95 −0.005），结构更小，且小目标更好、平衡度最高（0.448）。
- V3（减宽）参数 −33%，整体 m95 −0.015，性价比不错。
- V1/**V4 去 P5 明显伤大目标**（large 0.671->0.579），整体代价大。
- 推荐：质量优先选 **V2**；更省算力选 **V3**。

输出契约（重要）
----------------
输入：640x640 RGB uint8 NHWC；RKNN 预处理 mean=0 std=255
reg_max=16；锚点 (grid+0.5)*stride；图内无 DFL softmax/投影、无 sigmoid、无 NMS

- V0 / V2 / V3（3 尺度，6 输出）：
    box_p3 (1,64,80,80) box_p4 (1,64,40,40) box_p5 (1,64,20,20)
    cls_p3 (1,3,80,80)  cls_p4 (1,3,40,40)  cls_p5 (1,3,20,20)
- V1 / V4（2 尺度，4 输出）：
    box_p3 (1,64,80,80) box_p4 (1,64,40,40)
    cls_p3 (1,3,80,80)  cls_p4 (1,3,40,40)
  ⚠️ 端侧 detview 必须支持 2 尺度（nl=2，4 输出）才能解码 V1/V4；当前 detview 按 3 尺度配对，
    直接用会解码错误。

文件
----
 det-yolov8n-3cls-wb_v0_base-rk3568-raw-dfl6-int8.rknn
 det-yolov8n-3cls-wb_v1_nop5-rk3568-raw-dfl6-int8.rknn
 det-yolov8n-3cls-wb_v2_rep1-rk3568-raw-dfl6-int8.rknn
 det-yolov8n-3cls-wb_v3_w20-rk3568-raw-dfl6-int8.rknn
 det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn
 wb_v*_raw_dfl6_clip10.onnx                      各变体 raw-Dfl6 ONNX（clip10）
 SHA256SUMS.txt

校准：export/calib_zebra640_merged_v3.txt（500 张 merged 训练图）
训练：从零 150 epoch，SGD lr0=0.01，imgsz 640，batch16，close_mosaic20

⚠️ 提速提示
-----------
RK3568 为 DDR 带宽受限：**GFLOPs/层数下降不保证 NPU 时间等比下降**（已实测 reg_max 只省输出 IO、
NPU 时间不变）。请按 docs/RK3568_PROFILING.md 在板端测 V0/V2/V3 的纯 NPU 时间再定选型。
