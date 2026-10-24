# Release-3.2.0a

本发布收录 **PGL50H（50H）**、**PG2L100H（100H）** 与 **RK3568** 三套核心源码、有效约束与精简验证凭据，用于 C5 720P / C6 原生 640x480 的当前板验版本。**只含源码，不含位流、厂商 IP、仿真数据库或历史构建产物。**

- 仓库：`NineSun7579/fpga`（私有），默认分支 `main`
- 标签：`Release-3.2.0a`
- 器件与工具：PGL50H-6FBG484 / PG2L100H-6FBG484，PDS 2022.2-SP6.4
- 每文件 SHA-256 见 `SOURCE_MANIFEST.json`；每个子包目录下另有分项清单。

## 目录

| 路径 | 内容 |
|---|---|
| `fpga50/` | PGL50H C5/C6 有效 RTL、约束与最终 `seed22` 构建脚本 |
| `fpga50/evidence/` | 时序、四组回归、JTAG 编程与 C5/C6 原始帧哈希 |
| `fpga100/` | PG2L100H C5 接收/光学运行时、SFP、PCIe、显示与约束 |
| `fpga100/evidence/` | 时序、36 组回归、启动/上板核对摘要 |
| `rk3568/host/` | detview 主机源码（设置页行号复位 + 启动 mailbox 快照重试） |
| `rk3568/evidence/` | 两项自测与 UI 720P 切换板验摘要 |

## 50H 说明

`fpga50/build.tcl` 即最终烧录位流 `2a664888…` 的构建脚本，已把两条 C5 约束改为包内相对路径，`pnr -gplace_seed 22`、编译/综合/时序/位流步骤原样保留。`source/rtl/` 下 46 个文件与 `integration_receipt.json` 记录的回归输入逐字节一致（例如 `c6_coherent_framebuffer.v=6a02aa92…`、`cam5_cached_merge.v=5daf9411…`）。

构建前需把 `build.tcl` 中的厂商 IP（`pll/wr_fram_buf/rd_fram_buf/DDR3_50H/hsst_test`）放到 `source/rtl/` 相应位置；这些是 PDS 生成 IP，本包不包含。有效约束仅为 `constraints_c5/` 下两份 FDC（加 `hdmi_in_mes50hp.fdc`）。

## 100H 说明

`fpga100/source/` 与 `fpga100/constraints/` 按最终 `100_20261023T015913_006563Z` 工程的 `(_file ...)` 登记逐一收集，保留 donor 子目录以区分同名不同来源文件。厂商 IP 资源未收录；重建 `project.pds` 需在 PDS 2022.2-SP6.4 中按 `SOURCE_MANIFEST.json` 的 origin 与 vendor 环境重建。

## RK3568 说明

`rk3568/host/viewer/detview.pro` 是 qmake 工程（Qt5 Widgets + OpenCV4 + `-lrknnrt -lrga`）。板端构建：

```sh
mkdir build && cd build
qmake ../host/viewer/detview.pro
make -j2
```

硬件无关自测：

```sh
python3 host/run_tests.py          # C5 transaction + camera DMA 独立测试
./detview_motion_cam134 --touch-selftest
./detview_motion_cam134 --c5-runtime-selftest
```

UI 720P 手动操作：`Tab` → `↓`×6 → `→`×3 选 C5 → `↓`×1 → `→`。

## 板验摘要

- 50H：`All Constraints Met`（`timing_review.json`），四组冻结回归全 PASS（61 输入哈希一致）；位流 `2a664888f2a7cd32a8e1820f45e99a4ef57b1fdd5acb7728b606e2af8d513b82` 已编程、verify、读回逐字节一致、reload 后 `done=1`。C5 三帧 1280x720 原生、C6 三帧 640x480 原生且行唯一。
- 100H：`All Constraints Met`，36 组独立回归全 PASS。
- RK3568：`TOUCH_SELFTEST_PASS`、`C5_RUNTIME_SELFTEST_PASS`；UI 实际切换得到 `resolutionChanged camera=5 hd=1 ok=1`，C5 1280x720 约 11.2fps、C6 640x480 约 11.2fps、六路 `err=0/0/0/0/0/0`、`unstable=0`。

详见各 `evidence/` 文件；不含板上原生帧文件，仅保留其清单哈希。
