# 双目 demo 开发验证记录

## 环境与边界

RK3568实板：内核6.1.99，GCC12.2.0，OpenCV4.6.0，Qt5.15.8。使用用户提供的局域网SSH连接，源码与构建放在隔离目录：

```text
/userdata/linaro/detview-stereo-demo-work/src
/userdata/linaro/detview-stereo-demo-work/build/detview_stereo_demo
```

已检查依赖并构建运行**离线合成数据测试**；没有打开PCIe驱动、启动真实相机测距、更改FPGA或替换现有detview。真实配对相机、标定、曝光同步与共同帧号语义仍待提供。

## 验证内容

- CMake Release构建成功，启用`-Wall -Wextra -Wpedantic`。
- `stereo_geometry_and_matching`：真实SGBM恢复已知像素平移、2m合成深度；半分辨率和奇数尺寸保持深度；处理主点偏移；拒绝空白图、非法ROI、非法标定/参数/输入；YAML明确区分米、毫米和缺失单位。
- 自测还覆盖跨触发帧号配对、未知对应帧拒绝、计数回绕、显式offset和已消费帧拒绝。这里只验证软件帧号选择，不验证实板标签含义。
- `stereo_synthetic_headless`：保存预览、原图、视差、掩码与测量记录，ROI恢复2.000m。
- `stereo_uncalibrated_headless`：可导出视差，但`metric_valid=0`，记录中没有`axial_depth_meters`。
- `stereo_reject_empty_calibration`：拒绝零焦距、零基线的空模板。

测试输出与预览保存在 [验证日志目录](../../logs/stereo_demo_validation/)。[合成预览](../../logs/stereo_demo_validation/preview.png)明确标注SIMULATION，不能作为实物测距结果。

## 板端算法耗时

对同一张640×480合成图重复匹配5次，默认2个OpenCV线程；以下均值排除第一笔。不包含PCIe采集、图形显示和RKNN推理，不代表实时总帧率。

| 设置 | 输出尺寸 | 匹配平均耗时 | 恢复的合成ROI深度 |
| --- | --- | --- | --- |
| scale=0.5，numDisparities=64 | 320×240 | 257.01ms | 2.000m |
| scale=0.25，numDisparities=32 | 160×120 | 37.73ms | 2.000m |

第一轮实时demo建议从160×120开始；高分辨率应降低测距更新频率或进一步优化匹配。降低分辨率会降低视差精度，静态实物的误差和距离范围必须通过标定及现场测试确定。上述仅5次合成样本，未做长时间性能或负载稳定性测试。

## 尚未验证

真实双目输入、GUI鼠标/键盘交互、实物精度、运动目标同步误差、实板帧元数据约定与长时间PCIe/CPU并行负载。真实测试按用户后续指定的参数与时机进行。
