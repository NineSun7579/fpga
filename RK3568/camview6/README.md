# RK3568 六路 camview

RK3568 板端使用的 **六路 (CAM1~CAM6) 视频预览程序**，Qt 实现。

## 文件说明

| 文件 | 用途 |
|---|---|
| `main.cpp` | 主程序（六路 DDR 帧地址映射 + 双缓冲切换 + UI） |
| `dma_copy.h` | DMA 拷贝接口 |
| `camview.pro` | qmake 工程文件 |
| `patch_camview6.py` / `patch_camview6b.py` | 六路改造补丁脚本（记录如何从三路版本升级） |
| `benchmark_dma_copy.cpp` | DMA 拷贝带宽基准测试 |
| `send_key.py` | 远程按键注入辅助脚本 |

## 六路帧地址（DDR）

```
CAM1: 0x00A00000 / 0x00800000      CAM4: 0x01400000 / 0x01600000
CAM2: 0x00C00000 / 0x00E00000      CAM5: 0x01800000 / 0x01A00000
CAM3: 0x01000000 / 0x01200000      CAM6: 0x01C00000 / 0x01E00000
```

每路双缓冲（`*_ADDR_1` / `*_ADDR_2`），寄存器窗口 `R_CAMx_ACK/EN/ADDR1/ADDR2`。

## 编译

```bash
qmake camview.pro
make -j4
```

## 版本关系

- `RK3568/camview/` —— 旧的**三路**版本（CAM1/2/3），保留作为历史参考
- `fpga/host/camview/` —— 本目录的**上游源码**，两处内容应保持同步
