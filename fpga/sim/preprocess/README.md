# 预处理 IP 仿真验证 (任务 5)

## 快速开始

```bash
# 快速回归 (64x36, ~1分钟)
./run_all.sh

# 全分辨率回归 (640x360, ~5分钟, 23万像素逐像素比对)
./run_all.sh 640 360

# 1920x1080 压力回归 (golden 生成较慢)
./run_all.sh 1920 1080
```

依赖: ModelSim (默认 `C:\modeltech64_10.6e\win64`, 可用环境变量 `MODELSIM_BIN`
覆盖) + Python 3 (golden 生成)。

## 文件结构

```
golden_gen.py          Python golden 生成器 (与 RTL 逐位同源的行为模型)
tb_rgb2gray.v          rgb2gray 单元 TB (随机 valid 间隔 + X 传播检查)
tb_colorize.v          色化单元 TB (三标准色命中覆盖点)
tb_sobel_edge.v        Sobel 单元 TB (帧尾哑像素契约)
tb_preprocess_top.v    整链 TB (4模式+旁路+FIFO随机反压)
tb_prep_regs.v         AXI-Lite 寄存器 TB (BFM: 默认值/写读/脉冲/W1C/打点)
tb_button_debounce.v   按键消抖 TB (毛刺滤除/接受/toggle 单拍)
run_all.sh             一键回归 (golden 生成→编译→7 用例)
golden/                生成的激励与期望文件 ($readmemh)
log_*.txt              各用例最近日志
```

## 覆盖点 (对照任务 5 标准)

- 定向激励: 红/黄/绿标准色球 + 饱和度边界像素 + 明暗条纹 (边缘强响应)
- 功能覆盖: 三标准色命中计数、边缘命中计数、反压发生计数、灰度命中
- 断言: FIFO 无溢出 (上游尊重 s_ready)、无 X 传播、valid-only 契约
- 分辨率参数化: 640/1280/1920 行宽 (MAX_WIDTH=1920 编译期参数)

## 已验证结论 (2026-09-11 更新)

- 64×36 与 640×360 双分辨率 7/7 全 PASS (v ≈23 万像素逐位比对)
- 64/640/1920 三档分辨率 **10/10 全 PASS** (含 mode1/2/3 真实覆盖 + compare.py 逐位比对)
- 修复: tb_preprocess_top 的 r_mode 此前未随 MODE 赋值, mode1/2/3 从未被真正仿真过 (2026-09-11 抓出并修复)
- golden 契约要点 (RTL 与主机侧必须同源, 详见 DOC/FPGA_RK3568_传输协议_v1.md):
  - 灰度: `Y=(77R+150G+29B)>>8`, 5/6→8bit 高位复制
  - 色化: chroma<THR_SAT→灰度; R主→F800; G主→07E0; 黄→FFE0; 其余灰度
  - Sobel: 内部像素 (1..H-2, 1..W-2), mag=|Gx|+|Gy|, 二值门限
  - 上游契约: 每帧 H*W+1 像素 (帧尾 1 哑像素); s_valid 单拍语义

## 仿真中发现并修复的 RTL bug (回归价值记录)

| # | Bug | 影响 | 修复 |
|---|---|---|---|
| 1 | 5/6→8bit 复制位选错+位宽错 | 灰度偏差 | {r5,r5[4:2]} 高位复制 |
| 2 | 无符号减法下溢 (g>r) | 误判红色 | 比较后再减 |
| 3 | 窗口移位方向反 | 窗口水平镜像+偏移1列 | 最新列进 w02/w12/w22 |
| 4 | `{2'b0,w}` 拼接≠2×w | Sobel ±2 系数失效 | 显式 2*() |
| 5 | |gx|+|gy| 11bit 溢出 | 大梯度边位翻转 | abs 后 12bit 无符号相加 |
| 6 | AXI aw_seen 重_arm | 同一笔写执行两次 | !bvalid 守卫 |
| 7 | 跨行边界窗口未屏蔽 | 行尾窗口混入下行 | 中心列内部判定 |
| 8 | CTRL 回读拼接 47bit | 读回值错 | 修正为 32bit |
| 9 | 新增 sync_fifo 与既有 npu/common/sync_fifo.v 重名 | 全工程编译将报 duplicate module | 更名 prep_sync_fifo (二次复核抓出) |
