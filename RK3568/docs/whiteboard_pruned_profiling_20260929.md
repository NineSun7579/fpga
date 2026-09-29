# 白板剪枝压缩模型（zebra/vehicle/person 三类）RK3568 逐层速度报告

日期：2026-09-29　板端：RK3568 + `pango_pci_driver`（六路位流）　口径：`yolo_project/docs/RK3568_PROFILING.md` + `whiteboard_3cls/README.txt`

## 0. 结论摘要

- README 的提示在实测中成立：**GFLOPs 下降不代表 NPU 时间等比下降**。
  - V1（6.30 GFLOPs）纯 NPU 24.84 ms，V3（6.38 GFLOPs）却要 29.35 ms——算力几乎相同，时间差 **18%**。
  - V3 参数减 33%、GFLOPs 减 28%，实测**比 V0 还慢 1.8%**：减宽后小通道卷积的 NPU 效率下降，且 `Concat`/`Add`/`Split` 这类 DDR 相关算子耗时反而上升（Concat 4.12→5.49 ms）。
- **提速最明显的两档都是"去掉 P5 尺度"**（V1/V4），本质是少了 1/3 的层与 1/3 的输出 IO，而不是"参数少"。
- 质量/速度的折中：**V2 只掉 0.005 mAP50-95，换 1.38 ms（-4.8%）**，性价比最好；**V3 不推荐**（掉 0.015 mAP 还更慢）；V1/V4 最快但要接受大目标明显变差（large 0.671→0.579）。
- 固定成本：首层 `model.0/conv` 就要 **2.19–2.40 ms**（640×640×3 → 320×320×16），这部分任何变体都省不掉；`OutputOperator`（每尺度 6 个输出）只有 0.37–0.38 ms，但 `want_float=1` 的输出反量化 + 搬运让 run+io 比纯 run 多 **5.7–7.7 ms**。
- detview 端侧：V1/V4 只有 **4 个输出（2 尺度）**，README 声明旧版 detview 会解码错误；**当前 detview（按 (h,w) 通用配对、stride=640/w 推导）实测可正常解码**，已在板上检出 `3cls-wb_v4_combo:zebra 0.51`。

## 1. 测量口径

- **整机空闲**：测量前停掉 detview/camview（PROFILING.md 记录过不空闲会把 26 ms 测成 44 ms）。
- governor：`fde40000.npu` = performance，`dmc` = performance。
- 工具与参数（均为板端现成工具，源文件在 `/root/npu/`）：
  - `probe_shapes <model.rknn>`：输入/输出个数与形状。
  - `probe_quant <model.rknn>`：每路输出的 `type/qnt_type/scale/zp` 与隐含值域。
  - `bench_perf <model.rknn>`：`RKNN_FLAG_COLLECT_PERF_MASK` + 3 次预热，输出 `perf_run` 与 **逐层表**（ID/OpType/DataType/Target/Shape/Cycles/Time(us)/MacUsage/RW/FullName）。
  - `bench_yolo <model.rknn> 100 1|0`：100 次 `rknn_run` 的 min/mean/max；`want_float=1/0` 分别对应"反量化输出"和"纯 int8 输出"。
- 说明：逐层表带插桩开销，**逐层合计（28–37 ms）大于纯 NPU 实测（24–29 ms）**，因此逐层数据只用于**相对比较**（哪些层/哪类算子贵），绝对速度以 `bench_yolo` 的纯 NPU 为准。

## 2. 模型与 README 质量数据

| 变体 | 削法 | 参数(M) | GFLOPs | RKNN | mAP50/m95 | small | medium | large | 平衡(HM) | 输出 |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| V0 base | stock yolov8n | 3.157 | 8.86 | 4.2M | 0.8689/0.5544 | 0.2741 | 0.4526 | 0.6709 | 0.408 | 6（3 尺度） |
| V2 rep1 | C2f 重复全降 1 | 2.909 | 7.66 | 4.1M | 0.8598/0.5496 | 0.3510 | 0.4248 | 0.6720 | 0.448 | 6（3 尺度） |
| V3 w20 | 宽度 0.25→0.20 | 2.125 | 6.38 | 3.6M | 0.8603/0.5399 | 0.2781 | 0.4401 | 0.6496 | 0.405 | 6（3 尺度） |
| V1 noP5 | 去 P5，P3/P4 双尺度 | 0.970 | 6.30 | 2.0M | 0.8265/0.4914 | 0.2869 | 0.4079 | 0.5791 | 0.391 | 4（2 尺度） |
| V4 combo | 去P5+重复1+宽0.20 | 0.659 | 4.71 | 1.8M | 0.7997/0.4694 | 0.2709 | 0.3692 | 0.5780 | 0.369 | 4（2 尺度） |
| REF 预训练 | merged_v3_ft（对照） | 3.157 | 8.86 | — | 0.8590/0.5571 | 0.2897 | 0.4509 | 0.6744 | 0.419 | 6 |

（mAP 数据来自 `whiteboard_3cls/README.txt`，val 1952 图 / 9154 框；本次板端另测了 `zebra-merged-v3-rm8` 作为"现有线上模型"对照。）

## 3. 板端实测总表（100 次，want_float=1）

| 变体 | 输出 | 纯 NPU 均值 | min–max | run+io | RKNN 层数 | 逐层合计（插桩） | 相对 V0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V0 base | 6 | 28.83 ms（34.7 fps） | 27.30–29.36 | 36.13 ms | 102 | 34.77 ms | — |
| V1 noP5 | 4 | 24.84 ms（40.3 fps） | 24.65–25.21 | 31.76 ms | 70 | 29.47 ms | **−13.8%** |
| V2 rep1 | 6 | 27.45 ms（36.4 fps） | 26.62–27.85 | 34.71 ms | 96 | 31.38 ms | **−4.8%** |
| V3 w20 | 6 | 29.35 ms（34.1 fps） | 28.25–29.77 | 36.51 ms | 102 | 36.80 ms | **+1.8%** |
| V4 combo | 4 | **24.49 ms（40.8 fps）** | 23.40–24.82 | 32.16 ms | 64 | 28.46 ms | **−15.1%** |
| REF rm8（线上） | 6 | 28.24 ms（35.4 fps） | 27.39–28.73 | 33.90 ms | 102 | 36.46 ms | −2.0% |

`perf_run`（插桩口径）分别为 45093 / 36347 / 38149 / 45496 / 34989 / 43856 µs，排序与纯 NPU 一致。

## 4. 按算子类型分解（逐层合计，括号内为层数）

| 算子 | V0 base | V1 noP5 | V2 rep1 | V3 w20 | V4 combo | REF rm8 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ConvExSwish | 24.45（57） | 20.51（39） | 22.31（53） | 24.47（57） | 18.96（35） | 25.78（57） |
| Concat | 4.12（13） | 3.22（8） | 3.71（13） | **5.49（13）** | 4.05（8） | 4.35（13） |
| Add | 1.78（6） | 1.52（5） | 1.23（4） | 2.09（6） | 1.07（3） | 1.74（6） |
| Split | 1.61（8） | 1.24（5） | 1.76（8） | 2.16（8） | 1.77（5） | 1.84（8） |
| ConvClip | 1.31（6） | 1.21（4） | 1.13（6） | 1.30（6） | 1.01（4） | 1.28（6） |
| Resize | 0.66（2） | 0.45（1） | 0.51（2） | 0.45（2） | 0.40（1） | 0.62（2） |
| MaxPool | 0.46（3） | 0.95（3） | 0.32（3） | 0.44（3） | 0.81（3） | 0.59（3） |
| OutputOperator | 0.37（6） | 0.37（4） | 0.38（6） | 0.38（6） | 0.38（4） | 0.25（6） |
| InputOperator | 0.01（1） | 0.01（1） | 0.01（1） | 0.01（1） | 0.01（1） | 0.01（1） |

要点：

- `ConvExSwish` 占 67–71%，是绝对大头；它的下降基本只来自"层数/尺度数"（V1/V4 少 18–22 层）而不是"通道变窄"（V3 与 V0 同为 57 层、耗时几乎相同）。
- **V3 更慢的原因在 DDR 类算子**：`Concat` 4.12→5.49 ms（+33%）、`Add` 1.78→2.09、`Split` 1.61→2.16。通道变窄后每笔搬运的数据量没降多少，但小通道算子的访存效率更差。
- V1 与 V4 的 `MaxPool` 反而比 V0 高（0.95 / 0.81 vs 0.46 ms），说明去掉 P5 后 SPPF 的形态变了，但这部分总量很小。

## 5. 各模型最慢 8 层（逐层表节选）

**V0 base**（102 层）
- 2.21 ms ConvExSwish `model.0/conv`　- 1.31 ms `model.1/conv`　- 1.01 ms `model.2/cv1`　- 1.00 ms `model.2/cv2`
- 0.74 ms Concat `model.14/Concat`　- 0.70 ms `model.15/cv1`　- 0.69 ms ConvExSwish `cv3.0/cv3.0.0`　- 0.65 ms `model.4/cv2`

**V1 noP5**（70 层）
- 2.31 ms `model.0/conv`　- 1.14 ms `model.1/conv`　- 1.01 ms `model.2/cv2`　- 1.00 ms `model.2/cv1`
- 0.79 ms Concat `model.9/Concat`　- 0.77 ms `model.10/cv1`　- 0.70 ms `model.4/cv2`　- 0.69 ms `cv3.0/cv3.0.1`

**V2 rep1**（96 层）
- 2.29 ms `model.0/conv`　- 1.22 ms `model.1/conv`　- 1.02 ms `model.2/cv2`　- 1.00 ms `model.2/cv1`
- 0.77 ms `model.15/cv1`　- 0.71 ms `cv2.0/cv2.0.1`　- 0.65 ms Concat `model.14/Concat`　- 0.64 ms `cv2.0/cv2.0.0`

**V3 w20**（102 层）
- 2.31 ms `model.0/conv`　- 1.30 ms `model.1/conv`　- 1.04 ms `model.2/cv1`　- 1.04 ms `model.2/cv2`
- 0.89 ms Concat `model.4/Concat`　- 0.74 ms `model.4/cv2`　- 0.70 ms Concat `model.15/Concat`　- 0.68 ms `cv2.0/cv2.0.0`

**V4 combo**（64 层）
- 2.19 ms `model.0/conv`　- 1.14 ms `model.1/conv`　- 1.01 ms `model.2/cv2`　- 1.01 ms `model.2/cv1`
- 0.81 ms `model.10/cv1`　- 0.71 ms Concat `model.10/Concat`　- 0.70 ms `cv2.0/cv2.0.0`　- 0.69 ms `cv2.0/cv2.0.1`

**REF zebra-merged-v3-rm8**（102 层）
- 2.40 ms `model.0/conv`　- 1.25 ms `model.1/conv`　- 1.08 ms `model.2/cv1`　- 1.06 ms `model.2/cv2`
- 0.77 ms `model.15/cv1`　- 0.76 ms Concat `model.14/Concat`　- 0.69 ms `cv2.0/cv2.0.1`　- 0.69 ms `cv3.0/cv3.0.0`

观察：前 4 层（`model.0/conv` 下采样 + `model.1` + 两个 `model.2` 卷积）在**所有变体里都占约 5.5 ms**，是统一的地基成本；变体差异主要集中在尾部（P4/P5 分支与 Concat）。

## 6. 输出契约与量化核对（probe_shapes / probe_quant）

- 输入：`1×640×640×3`，INT8，affine scale=0.00392157（=1/255）、zp=−128 → 值域 [0,1]，与 README 的 `mean=0 std=255` 一致。
- 输出（顺序与 README 契约一致）：
  - V0/V2/V3：`box_p3 (1,64,80,80) / box_p4 (1,64,40,40) / box_p5 (1,64,20,20) / cls_p3 (1,3,80,80) / cls_p4 / cls_p5`
  - V1/V4：`box_p3 / box_p4 / cls_p3 / cls_p4`（**2 尺度**）
- 量化：全部 `INT8 / AFFINE_ASYM`；`box` 各路 scale≈0.062–0.078（DFL logits，值域 ±10，分辨率充足）；`cls` scale≈0.047–0.050（logits，端侧再做 sigmoid）。
- 对照：线上 `zebra-merged-v3-rm8` 的 `box` 是 **32 通道/尺度**（reg_max=8），本次白板组是 **64 通道/尺度**（reg_max=16）——同一分辨率下白板组的输出 IO 更大。
- **detview 兼容性实测**：V1/V4 的 4 输出（2 尺度）在当前 detview 上可正常加载与解码（`[model] … OK 4 outputs cached`，画面检出 `3cls-wb_v4_combo:zebra 0.51`）；README 中"必须支持 2 尺度"的警告针对旧版按 3 尺度硬配对的实现，现已不适用。

## 7. 应用内端到端对照（detview，六路 3×2 + 两款轮换，非空机）

| 模型 | 应用内单次耗时 | 纯 NPU（本报告） | 差值（pre+IO+post+排队） |
| --- | ---: | ---: | ---: |
| zebra-rk3568-raw-dfl6 | 43–49 ms | 28.83 ms（V0 同级 3 尺度/64 通道） | ~14–20 ms |
| wb_v4_combo | 41 ms | 24.49 ms | ~16 ms |

差值与应用侧 letterbox 预处理、`want_float` 反量化、DFL 解码 + NMS、以及共享 DMA/显示竞争有关；两个模型的差值接近，说明**模型侧排序可以直接带到端到端**（V4 比 3 尺度大模型快约 4 ms）。

## 8. 选型建议

1. **质量优先**：V2（−0.005 mAP50-95 / −1.38 ms）；若要多路且算力紧，V2 是唯一"几乎白拿"的加速。
2. **速度优先、可接受大目标变差**：V4 combo（−15.1% 时间，24.49 ms），或 V1。
3. **不建议 V3**：参数/体积下降最多，但时间反而 +1.8%，除非显存/存储是硬约束。
4. 想更快应优先**减少尺度数（去 P5）或减少模型数**，而不是继续减宽——本组实测已证明减宽在 RK3568 上不划算。
5. 若沿用 reg_max=8（如线上 rm8 的 32 通道输出），输出 IO 还能再省一部分，可作为下一步对照实验。

## 9. 复现与原始数据

```sh
# 板端（先停 detview/camview，确认 governor=performance）
/root/npu/probe_shapes <model.rknn>
/root/npu/probe_quant  <model.rknn>
/root/npu/bench_perf   <model.rknn>          # 逐层表 + perf_run
/root/npu/bench_yolo   <model.rknn> 100 1    # 纯 NPU min/mean/max（反量化输出）
/root/npu/bench_yolo   <model.rknn> 100 0    # 纯 int8 输出
```

原始日志：`RK3568/docs/whiteboard_profiling/raw/<变体>.{shapes,quant,perf,yolo_f1,yolo_f0}.txt`（6 个变体 × 5 个文件，板端生成于 `/userdata/linaro/whiteboard_prof_20260929/`）。
模型：`RK3568/docs/` 同级说明见 `whiteboard_3cls/README.txt`（WebDAV `yolo_project/whiteboard_3cls/`），板端部署于 `/root/npu/whiteboard_3cls/`。
