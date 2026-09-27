# RK3568 detview 模型说明

本目录归档三个 YOLOv8n RKNN INT8 检测模型，输入分辨率均为 640 × 640。它们的检测任务和输出协议不同，调用方需要按对应格式解码，并使用与训练时一致的预处理。仓库目录用于发布；板端 `detview` 只扫描其部署目录，不会自动扫描这里。

| 模型 | 检测目标 | 输出与解码 | 适用场景 |
| --- | --- | --- | --- |
| `det-yolov8n-tt100k-crop640-rk3568-raw-dfl6-int8.rknn` | TT100K 29 类交通标志 | 6 路：P3/P4/P5 各一组 DFL box logits 与分类；端侧完成 DFL 和 NMS | 已裁剪、标志被放大的 640 × 640 ROI |
| `det-yolov8n-zebra-rk3568-raw-dfl6-int8.rknn` | `zebra`、`vehicle`、`person`，按此顺序 | 6 路：P3/P4/P5 的 DFL box logits 与 3 类分类；端侧完成 DFL 和 NMS | 斑马线场景，优先考虑推理吞吐量 |
| `det-yolov8n-zebra-rk3568-int8-split.rknn` | 同上，3 类 | 2 路：box `[1,4,8400]` 与分类 `[1,3,8400]`；模型内完成 DFL，端侧完成后续筛选与 NMS | 需要使用已有双输出解码接口时 |

## 选择与性能

两个 zebra 模型执行相同的三类任务，**不可仅按文件名把输出互换**。`raw-dfl6` 的 box 是每个位置 4 × 16 个 DFL logits，三个尺度分别为 80 × 80、40 × 40、20 × 20；`int8-split` 的 box 已变为 8400 个位置的 4 个坐标。板端历史 `bench_yolo` 记录显示 zebra `raw-dfl6` 纯 NPU 约 27.95 ms/次（35.8 fps）；这是基准程序结果，不代表带采集、缩放和显示的 `detview` 帧率。`int8-split` 的图内 DFL 路径通常更慢，具体速度以同一板卡上的实测为准。

TT100K crop640 模型只在**以目标为中心的裁剪图**上训练，不建议直接用于完整 2048 × 2048 图像缩小到 640 × 640 的检测。模型包记录：在 5338 张 crop test 图上，RKNN INT8 的 mAP50 为 0.946、mAP50-95 为 0.711；完整图像验证集的 mAP50 为 0.503，属于不同输入条件，不能直接比较。其六路输出形状中，box 为 `[1,64,80/40/20,80/40/20]`，分类通道数为 29。

## 在 detview 中使用

当前板端 `detview` 扫描 `/root/npu/yolov8n/zebra640` 和 `/root/npu/tt100k_yolov8n` 等部署目录。把模型复制到对应目录后，可用 `--model crop640`、`--model zebra-rk3568-raw-dfl6` 或 `--model zebra-rk3568-int8-split` 按路径子串选择；先检查日志和界面中实际加载的模型。crop640 模型仍需要上游提供合适的 ROI，选择模型本身不会自动裁剪目标。

## 文件校验

| 文件简称 | SHA-256 |
| --- | --- |
| TT100K crop640 raw-dfl6 | `755b63de66a72f96a6b117ec215964521a2271a9d8719443bf63bb6a2711e68a` |
| zebra raw-dfl6 | `ad97e9189ae1472c3ab0d2bfdc023c9a2f17d75eb471563be6f0706c956bfe88` |
| zebra int8-split | `ab2e56bca67e85e855677d862bea552cd28fd7bb75f5bf99e041622b5cd9b4a7` |
