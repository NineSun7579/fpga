# NPU 软硬件一致性验证报告 (sim/npu/compare.py)

逐位比对: npu_golden.py 黄金期望 vs TB 落盘 hw_out_*.mem ('x' = don't care 跳过)

| 流 | exp | hw | 不一致 | skipped(x) | 结果 |
|---|---|---|---|---|---|
| cat_add      (3尺度区+cat分时+0.5舍入边界) | 93 | 93 | 0 | 0 | ✓ |
| conv11_conv  (1x1 核原始累加 24bit) | 320 | 320 | 0 | 16 | ✓ |
| conv_conv    (3x3 核原始累加 24bit) | 128 | 128 | 0 | 0 | ✓ |
| sppf_maxpool (5x5 stride5 无符号 max) | 160 | 160 | 0 | 0 | ✓ |
| upsample_top (nearest 2x 模块级) | 192 | 192 | 0 | 0 | ✓ |
| conv_top     (3x3 完整量化模块级) | 48 | 48 | 0 | 0 | ✓ |
| conv11_para  (1x1 完整量化+out_buf) | 48 | 24 | 0 | 0 | ✓ |

## 结论

**ALL PASS**: 全部流逐位一致 ✓