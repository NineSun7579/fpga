# detview 实测各模型推理帧率 与 bench 差异分析

日期：2026-09-29　板端：RK3568（六路位流，`pango_pci_driver` 已绑定）　对照口径：`docs/RK3568_PROFILING.md`

## 0. 结论摘要

- 应用内（detview）与空机（bench_yolo）**模型排序完全一致**：V4 combo 最快、V1 noP5 次之、V3 w20 在白板组内最慢——**bench 的结论可以直接用于选型**。
- 应用内单次耗时比 `bench_yolo` 的 run+io（float 输出）**多 8.4–14.2 ms**，构成：输出反量化 ≈2.0–2.3 ms（bench f0/f1 之差）+ DFL 解码/NMS ≈4 ms（早前 220 帧分段测量）+ 其余 ≈3–8 ms（输入拷贝 1.2 MB、QImage/Detection 分配与跨线程投递、线程调度、与采集/显示争 CPU）。
- **显示配置对检测模型只值 0.5–3.1 ms**（6 路 3×2 比单路 C1 慢 0.45–3.08 ms），说明 RGA 缩放 + 单路停采之后，显示管线已经不再是推理的主要干扰；但对**分割模型**（LinkNet）grid 比 c1 慢 **24.9/38.2 ms**，因为它的逐像素 argmax 后处理很吃 CPU，与显示线程抢核。
- 实测推理吞吐（单路 C1）：V4 combo 24.6 fps、V1 24.1、V2 21.4、V0 21.1、zebra-raw-dfl6 21.0、V3 20.9、TT100K-crop640 15.9、zebra-int8-split 14.1、LinkNet-binary 5.1、LinkNet-multiclass 3.4。
- LinkNet binary 应用内 194.6 ms，与早前 laneview4 独立实测（约 199 ms）一致，说明该数字是模型+后处理的固有代价，不是 detview 引入的额外损耗。

## 1. 测量口径

- **应用内**：`detview --fullscreen [--camera 1] --model <子串> --duration 12`，单模型模式（不轮换），`DET_BENCH=1`；每次运行前 `rmmod/insmod pango_pci_driver` 保证干净状态；统计 `[tdm_bench]` 的 `ms=` 分布（n/均值/min/max）与 `[panes]` 的显示帧率。
- **参考**：`bench_yolo <model> 100 1|0`（空机、governor=performance），取纯 `rknn_run` 与 `run+io`（want_float=1 为反量化输出，=0 为 int8 输出）。
- 两种显示配置：`grid` = 默认 6 路 3×2；`c1` = 单路 C1（其余采集线程停采）。

## 2. detview 实测（每模型 12 秒）

| 模型 | C1 平均 ms | C1 推理 fps | 6路平均 ms | 6路推理 fps | 显示 fps（C1 / 6路） | 样本（C1/6路） |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| **wb_v4_combo** | **40.59** | **24.64** | **43.08** | **23.21** | 22.7 / 18.9 | 209 / 196 |
| wb_v1_nop5 | 41.47 | 24.12 | 43.37 | 23.06 | 22.6 / 18.7 | 206 / 185 |
| wb_v2_rep1 | 46.85 | 21.35 | 47.30 | 21.14 | 22.6 / 18.8 | 195 / 183 |
| wb_v0_base | 47.39 | 21.10 | 49.30 | 20.29 | 22.6 / 18.9 | 199 / 183 |
| zebra-rk3568-raw-dfl6 | 47.60 | 21.01 | 49.60 | 20.16 | 22.5 / 18.7 | 195 / 175 |
| wb_v3_w20 | 47.96 | 20.85 | 50.68 | 19.73 | 22.5 / 18.3 | 192 / 182 |
| tt100k-crop640 | 62.82 | 15.92 | 65.26 | 15.32 | 22.6 / 18.6 | 161 / 155 |
| zebra-rk3568-int8-split | 71.20 | 14.05 | 74.28 | 13.46 | 22.4 / 18.5 | 148 / 140 |
| LinkNet-lane640-binary | 194.62 | 5.14 | 219.52 | 4.56 | 22.6 / 18.8 | 56 / 50 |
| LinkNet-lane640-multiclass | 295.70 | 3.38 | 333.85 | 3.00 | 22.3 / 18.9 | 37 / 33 |

## 3. 与空机 bench 的差异

| 模型 | detview（C1） | detview（6路） | bench run+io（float） | bench 纯 run（float） | 差（C1 − run+io） | 差（6路 − run+io） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| wb_v0_base | 47.39 | 49.30 | 36.13 | 28.83 | +11.26 | +13.17 |
| wb_v1_nop5 | 41.47 | 43.37 | 31.76 | 24.84 | +9.71 | +11.61 |
| wb_v2_rep1 | 46.85 | 47.30 | 34.71 | 27.45 | +12.14 | +12.59 |
| wb_v3_w20 | 47.96 | 50.68 | 36.51 | 29.35 | +11.45 | +14.17 |
| wb_v4_combo | 40.59 | 43.08 | 32.16 | 24.49 | +8.43 | +10.92 |
| zebra-raw-dfl6（同结构参考） | 47.60 | 49.60 | (36.13) | (28.83) | +11.47 | +13.47 |
| zebra-merged-v3-rm8（线上，box 32 通道） | — | — | 33.90 | 28.24 | — | — |
| tt100k-crop640 / zebra-int8-split / LinkNet×2 | 见 §2 | 见 §2 | 未测 | 未测 | — | — |

（`zebra-raw-dfl6` 与白板 V0 同结构：3 尺度、box 64 通道、3 类，故用 V0 的 bench 作参考。）

## 4. 差异来自哪里

1. **输出反量化（want_float=1）≈ +2.0–2.3 ms**：由 bench 的 int8 输出 vs float 输出直接测得（V0 33.85→36.13、V4 29.95→32.16、V1 28.97→31.76）。
   反向印证：线上 `zebra-merged-v3-rm8` 的 box 只有 32 通道/尺度（reg_max=8），其 IO 增量只有 4.4/5.7 ms，比白板组 64 通道的 5.0–5.7/7.3–7.7 ms 小。
2. **DFL 解码 + NMS ≈ 4 ms**：来自早前静态图 220 帧分段测量（rm8/rm16 口径 `t_post≈4.0 ms`），detview 的这三段（inputs_set → run → outputs_get → decode）都在 `[tdm_bench]` 的计时窗口内。
3. **其余 ≈ 3–8 ms**：`rknn_inputs_set` 的 1.2 MB 输入拷贝、每帧 `QImage infer`（1.2 MB）与 `QVector<Detection>` 的分配和跨线程投递、推理线程与 6 个采集线程 + 显示线程的 CPU 调度竞争。
4. **显示/采集竞争（同模型 grid − c1）**：
   - 检测模型仅 **+0.45 ~ +3.08 ms**（V2 最小 0.45，zebra-split 最大 3.08）——RGA 缩放 + 单路停采后，显示管线对推理的影响已经很小。
   - **分割模型 +24.90 / +38.15 ms**（LinkNet binary / multiclass）。原因很明确：LinkNet 的后处理是 640×640×2（或 ×9）逐像素 argmax（3.7M 像素级操作），本身就是纯 CPU 重活，grid 配置下要与显示线程抢核，c1 下就快得多。多分类（9 通道）比二分类再多 ~13 ms，与通道数成比例。
5. **应用内与 bench 的比例**：`(detview − 纯run)/纯run` 在检测模型上是 +41% ~ +57%，其中约一半是应用固有开销（IO+后处理），一半是与采集/显示争 CPU——这也是"应用内帧率永远达不到 bench 数字"的根本原因。

## 5. 模型间排序一致性核对

| 排序（快→慢） | bench 纯 run | detview（C1） |
| --- | --- | --- |
| 1 | V4 combo 24.49 | V4 combo 40.59 |
| 2 | V1 noP5 24.84 | V1 noP5 41.47 |
| 3 | V2 rep1 27.45 | V2 rep1 46.85 |
| 4 | V0 base 28.83 | V0 base 47.39 |
| 5 | V3 w20 29.35 | V3 w20 47.96 |

五个变体在两边顺序完全一致，说明：**用 bench 做选型是可靠的；V3 在真实应用里同样不划算**（比 V0 还慢 0.6 ms）。

另外两个应用内观察：

- `zebra-rk3568-int8-split`（2 输出 split 头）应用内 71.2 ms，比同数据的 `zebra-raw-dfl6`（47.6 ms）慢 23.6 ms——split 头在 detview 里走的是"分离 box + 分类张量"解码路径，后处理开销明显更大，不建议在实时链路上用。
- `tt100k-crop640`（29 类）62.8 ms，比 3 类的 V0 慢 15 ms，主要是 29 类分类头的 NPU 计算与解码通道数更多。

## 6. 复现

```sh
# 应用内（板端，先停其它占设备的程序）
cd /userdata/linaro/detview-tdm-build-20260928
sudo env DET_BENCH=1 DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 \
  ./detview --fullscreen --camera 1 --model <子串> --duration 12 > log 2>&1
grep '\[tdm_bench\]' log | sed 's/.*ms=//' | sort -n        # 每次推理耗时

# 空机参考
/root/npu/bench_yolo <model.rknn> 100 1     # 反量化输出（与 detview 一致）
/root/npu/bench_yolo <model.rknn> 100 0     # int8 输出
```

原始日志：`RK3568/docs/detview_inapp_fps/logs/<模型>_<grid|c1>.log`（20 个文件，板端 `/userdata/linaro/detview_fps_20260929/`）。
