# detview 双目测距 demo

这是 `detview_tdm` 的独立 C++ 原型：左/右图像 → 双目标定校正 → StereoSGBM → 左右一致性过滤 → ROI 中位深度。暂不改变现有 detview 的采集、显示和模型推理路径；算法与帧源分开，后续可接入 detview 的帧池和测距叠加层。

支持三种数据源：合成平行双目、离线左右图、FPGA PCIe 两路640×480 RGB565帧。无需RKNN模型，依赖OpenCV4的core/imgproc/imgcodecs/calib3d/highgui。默认半分辨率匹配，先控制RK3568 CPU开销；真实帧率尚待实测。

板端合成自测、算法耗时和验证边界见 [VALIDATION.md](VALIDATION.md)。低开销档`--scale 0.25 --num-disparities 32`的合成匹配均值约38ms；默认半分辨率约257ms，这些不包含真实采集、显示和推理。

## 构建与离线自测

板端已只读确认g++、OpenCV4.6.0、Qt5.15.8可用。测试合成数据不打开PCIe设备、不启动相机、不运行RKNN。

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
./build/detview_stereo_demo --self-test
./build/detview_stereo_demo --synthetic --headless --output ./synthetic_output
# 低开销档：离线重复计算5次，不访问相机
./build/detview_stereo_demo --synthetic --headless --scale 0.25 \
  --num-disparities 32 --benchmark 5 --output ./synthetic_output
```

合成数据用20px平移、400px焦距、0.1m基线构造2m平面；这些仅为测试夹具，不是相机参数。输出中明确标记 `simulation`。自测检查已知深度恢复、缩放后深度一致、无标定拒绝米数、空白图和非法参数拒绝。

有桌面环境时：

```sh
./build/detview_stereo_demo --synthetic
```

三个图窗区域依次为左图、右图、视差。拖动左图或视差区选择ROI；Q/Esc退出。`--output DIR`指定保存目录后，按S保存。未确认新帧持续到达时会遮盖旧距离并提示STALE。

## 离线实拍图片

```sh
./build/detview_stereo_demo --left-image left.png --right-image right.png
./build/detview_stereo_demo --left-image left.png --right-image right.png \
  --calibration stereo.yml --headless --output ./pair_result
```

未标定时只显示未经校正的图像和尝试匹配的视差，不显示米数；这时视差不能当作准确几何结果。离线实拍图必须来自同一曝光时刻、相同图像设置和对应标定分辨率。图片读取忽略EXIF方向，按存储像素坐标对应标定；不要混用旋转后图片与原始标定。提供标定后使用 `stereoRectify` 与 `remap`；只支持水平正视差双目，垂直双目和颠倒左右顺序被拒绝。

`--roi x,y,w,h`使用**缩放并校正后的左图像素坐标**，不是640×640模型输入坐标。默认ROI位于图像中间。`--scale 0.5`下640×480成为320×240；`--num-disparities 64`是处理图上的视差范围且必须为16的倍数；`--block-size 5`必须为奇数。放大视差范围会增加耗时并减少有效边缘区域。`--threads 2`默认限制OpenCV工作线程，可按板端负载调整。

## 待提供的相机参数

`calibration.template.yml`是不能直接使用的空模板：零焦距、零基线会被拒绝。请用实际双目标定结果填入：

| 参数 | 含义 |
| --- | --- |
| 左/右相机ID | 明确哪两路组成双目、左右顺序；不默认C1/C2 |
| image_width/image_height | 标定使用的原始分辨率，必须匹配输入 |
| K1、K2 | 左右3×3内参，焦距以像素计 |
| D1、D2 | OpenCV针孔模型畸变系数，不接受未转换的鱼眼模型 |
| R、T | 左相机到右相机的外参，T必须以米表示，`length_unit: m` |
| 同步方式 | 共触发/硬同步是否已确认；独立帧计数不能证明同步 |
| 帧计数对应关系 | 同次曝光的`left_tag - right_tag`，及两个标签是否确实表示共同曝光编号 |
| 测试距离与目标 | 待用户指定；先测静态有纹理目标，再判断运动目标误差 |

输出的 `axial_depth_meters` 是相机光轴方向Z，公式为 `fx × baseline / (disparity - cx_offset)`；不是到目标的三维直线距离。ROI应覆盖同一目标表面，避免前景/背景混合。左右一致性、有效像素数和比例用来拒绝不可靠ROI，不是精度保证；弱纹理、遮挡、反光和重复纹理仍会影响结果。

## FPGA双路输入：等待测试时机再运行

实时帧源复用当前六路DDR地址表，使用已验证的614400B整帧DMA与16B标签读取。启动时必须指定相机，不改写相机使能寄存器，也不自动停止现有应用。

```sh
# LEFT_ID / RIGHT_ID由实际双目配对决定。先停止现有采集及其守护程序。
sudo ./build/detview_stereo_demo --live \
  --left-camera LEFT_ID --right-camera RIGHT_ID --calibration stereo.yml
```

实时模式默认禁止输出米数，直到操作者已确认硬件曝光同步及共同曝光帧号关系，再显式追加 `--assume-synchronized --tag-offset N`，其中`N = left_tag - right_tag`，支持32位计数回绕。不能随意填0：独立自由运行的相机计数偶然相等也不证明同次曝光。这两个参数记录的是操作者确认，不会建立或验证硬件同步；标定仍必须提供。若相机标签没有共同曝光编号含义，应先修改FPGA帧元数据，保持demo仅预览视差。两路帧是顺序DMA读取，窗口中的host read gap仅是主机读取时间差，不能表示曝光时间差。

采集等待两路都有新标签；已提供共同计数关系时只选对应编号的槽位，避免标签读取期间新触发造成左N/右N+1错配。读后复查标签，拒绝标签变化期间的帧。标签并非曝光时间戳，甚至不能绝对排除正在写入但还未更新标签的缓冲，因此还需要确认FPGA乒乓槽写入和发布协议。采集与匹配在工作线程执行，只保留最新结果；GUI根据主机采集完成时间检查结果年龄，慢处理或断流超过2秒时隐藏旧距离。

当前驱动的open会清全局状态、close会释放全局DMA内存。demo先对独立锁文件加flock，再检查其他进程的设备句柄和mmap，最后open驱动，避免两个demo并发启动时互相破坏状态。但不能防止不遵守该锁的旧应用稍后启动；运行期间应保持设备独占，停掉采集守护程序。首次DMA错误即停止提交，不自动清标志重试；驱动在途传输取消与释放问题仍需驱动侧修复，不能把退出重开当作已验证的安全恢复。

## 输出与后续接入

保存 `preview.png`、`left_raw.png`/`right_raw.png`原图、左右处理图、视差彩色图、有效像素掩码和 `measurement.yml`。左右处理图仅在提供标定时做校正。记录包含相机ID、匹配设置、原始浮点视差、ROI、有效像素、校正后的几何参数、处理耗时、帧标签及host read gap；仅在测距有效时写入米数。相同输出目录的文件会被新快照覆盖。

算法入口是 `DepthEngine::compute()` / `estimate()`，FPGA输入入口是 `PangoStereoSource::poll()`。后续接入detview时应复用应用唯一的Pango设备实例，将成对帧送到测距工作线程；**不要在detview运行时再打开第二个PCIe句柄**。采用仅保留最新成对帧的队列，避免SGBM慢于采集时累积旧距离，并按各模型的letterbox映射将检测框转换到校正图ROI。
