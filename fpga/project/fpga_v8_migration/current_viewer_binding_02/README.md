# 当前查看器基线漂移只读审计

初始范围：仅本目录写入本地证据；板端仅 SSH `/proc`、sysfs、明确候选源码/构建路径的只读元数据与普通文件读取，以及 SFTP 下载。两次快照均记录 boot、PID/starttime/executable/hash/cmdline、RKNN maps 和全部可观察 Pango fd/maps 所有者。不会启动 viewer、推理、打开设备、ioctl、mmap、reset、停止进程、加载 FPGA、写入或构建板端文件。其他代理的 CaptureArm/PDS 工作不参与。

旧证据仍独立有效：driver_ownership_audit 的 PID149510 与 viewer_native_runtime_probe 的 PID2740 属于各自采集边界；本审计不会追溯替换其绑定。当前身份差异按外部漂移记录。

## 当前边界与外部漂移

最终完整快照为 `snapshot_02.json`、`snapshot_03.json`，板端采样时间间隔 159.949536 秒。两次遍历所有 `/proc/[0-9]*/fd` 和 maps，使用 root 只读权限，没有扫描错误；唯一观察到的设备所有者均为下述 viewer。两次 boot、starttime、exe、cmdline、设备 fd/maps、RKNN maps/hash、rknpu sysfs version 均相同。快照只能证明采样边界，不能证明期间没有短暂用户或内部 DMA 状态。

| 项目 | 两次结果 |
|---|---|
| boot UUID | `12803068-a3fb-4341-b05e-4f31921cfb1b` |
| 内核 | `6.1.99`，aarch64 |
| PID / start ticks | `2740` / `152164` |
| exe | `/userdata/detview-driving-demo/detview-driving-demo` |
| exe SHA256（读取 `/proc/2740/exe`） | `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4` |
| cwd | `/home/linaro` |
| 设备 fd | `17 -> /dev/pango_pci_driver` |
| 设备 maps | `7f76b43000-7f76f43000`、`7f76f43000-7f77343000`，各 4194304 字节，`rw-s`，offset 0 |
| Pango module | live / refcnt 2 |
| RKNN mapped path | `/usr/lib/librknnrt.so`，一个路径、四个 segment |
| runtime SHA256 | `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885` |
| `/sys/module/rknpu/version` | `0.9.8` |

命令行：

```
/userdata/detview-driving-demo/detview-driving-demo --driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo
```

RKNN segments 原样保存在两份 JSON 中：`7f8b180000-7f8b838000 r-xp`、`7f8b838000-7f8b848000 ---p`、`7f8b848000-7f8b879000 r--p`、`7f8b879000-7f8b87c000 rw-p`。

旧 driver_ownership_audit 记录 boot `d167174d-777b-4f93-bc1d-ea01ffc83a9a`、PID149510、hdmifull SHA `496acc4ffe4efe12d04629d8864b4bf4596d500d2980ee6ca7598aeb2a8685ae`。boot UUID 明确不同，说明已跨启动边界；具体外部部署者、时间和重启原因没有证据。本次没有导致该漂移。最新 runtime probe README 所述 PID2740/start152164/path 与本次一致；不能把旧 probe 中使用的冻结 decoder 误称为当前生产源码。

SDK/runtime **可观察部分未改变**：取回当前源码旁 `rknn_api.h` 的 SHA `c48e11a6f41b451a5fd1e4ad774ea60252d3d94f78bee9b21ea3d21b21deba9a` 与旧候选相同；mapped runtime SHA 与旧 probe 相同；rknpu sysfs version 两次均为 0.9.8。取回的 runtime 包含 API literal `2.3.0 (c949ad889d@2024-11-07T11:35:33)`。没有创建 RKNN context 或执行 API query，因此 API literal 是磁盘内容佐证，不能作为新一轮 live API 查询结果；也没有证明整套 SDK、驱动构建或 FPGA 镜像均未变。

`snapshot_01.json` 是初始宽匹配辅助快照，包含 Pango 字体库映射；字体库不是设备所有者。随后明确采用 `/dev/pango` 过滤，`snapshot_01_device.json` 与最终两份设备快照结果一致。辅助证据保留，不混入设备所有者计数。

## 当前源码、构建与 ELF 恢复

只扫描两个明确根目录（`discovery.json`），未搜索全盘。取回目录为本地 `inputs/userdata/linaro/detview-driving-demo-src/`，包含完整发现的源码、头文件、qmake pro/Makefile、moc 文件、对象文件、保留 ELF、构建日志与功能说明；另取回安装 ELF、runtime 及当前两模型和固定旧模型的文件/sidecar。共 **91 个下载文件**的远端 before SHA = 本地 SHA = 远端 after SHA，见 `retrieval_manifest.json`、`remote_hash_before.json`、`remote_hash_after.json`。原始发现共 85 个普通文件，模型/runtime 的追加选择由 `selection.json` 明列。

SFTP 无法读取 root 模型路径时，使用 SSH sudo 对明确 `.rknn`/JSON 普通文件只读读取并直接保存本地；没有板端 staging。`/proc/2740/exe` 的 SFTP 下载权限被拒绝，失败在 manifest 中保留，但 root SSH 的前后 SHA 均成功。安装 ELF 和源码目录 ELF 已取回，且都与该 proc exe 哈希相同，所以当前执行字节已有匹配的本地副本。

| 远端具体路径 | SHA256 |
|---|---|
| `/userdata/linaro/detview-driving-demo-src/main.cpp` | `1fb152cf8a5c964528bd9fea2d3a84ba0cf393a9848a98a84be65921a56e2a39` |
| `/userdata/linaro/detview-driving-demo-src/detview` | `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4` |
| `/userdata/detview-driving-demo/detview-driving-demo` | 同上 |
| `/userdata/linaro/detview-driving-demo-src/main.o` | `9cebd0717f206d4b86494e6cce03c2cfafcf28554cd6c2b5c54a71bd6f167a03` |
| `/userdata/linaro/detview-driving-demo-src/Makefile` | `6fb2b292013c88c41ff755d9781e6a53fae6cb20831ce00c6c3d30293f9eea74` |
| `/userdata/linaro/detview-driving-demo-src/detview.pro` | `26403125d791c22626f0bf063332d7c7a6770b0ab9561c6a9abd63da2af0f979` |
| `/userdata/linaro/detview-driving-demo-src/inference_geometry.h` | `85ef8b88c81da222c27f1269939740905d74e14b5e2fbda44c34f443d47333ac` |
| `/userdata/linaro/detview-driving-demo-src/driving_demo.cpp` | `3e87b8a0fe41ef9eca3dfdb9ffb0aff10a07530dc1d040b53f3eb5c1e8741331` |
| `/userdata/linaro/detview-driving-demo-src/driving_overlay.cpp` | `c533930d6092d0067fdf6bc641ce21882bef6f51ecee35367dad2f12f692f342` |

完整逐文件哈希与和旧 candidate 的同异列表见 `comparison.json`。冻结比较输入已复制到 `inputs/frozen_0301/` 并记录 `frozen_comparison_inputs.json`，不会修改原目录。

当前 ELF：1197400 字节、ELF64 little-endian AArch64 PIE，build ID `cd16b2bc3bb06554fd35c784ca625faea7c4b186`；`.comment` GCC Debian 12.2.0-14。Makefile 为 qmake 3.1/Qt 5.15.8，`-O2 -std=gnu++1z`，链接 RKNN、Qt Widgets/Gui/Core、OpenCV；DISTDIR 明确为 `/userdata/linaro/detview-driving-demo-src/.tmp/detview1.0.0`。当前 SOURCES/OBJECTS 包含 inference_geometry selftest、driving_demo、自测、driving_overlay/validation。所有相关保留构建日志已取回，日志属于外部历史构建。

`elf_sdk_model_metadata.json` 中 readelf/nm/窄范围 strings 确认编译 ELF 有 `scanModels`、`InferenceThread::tryDecodeDfl`、`decode`、`runOnce`、含 bool 参数的 `nmsAppend`、trafficlight 自测、geometry 自测和 DrivingDemo/overlay 符号；strings 也包含交通灯输入验证、canonical_y=network_y+80 和 class-aware NMS 文案。`compiled_codepaths.json` 保留上述函数的窄范围反汇编。NMS 在 `0x30cb0-0x30cc0` 按 bool 参数检查结果数大于 299 后退出，在 `0x30d38-0x30d48` 按 bool 参数比较类别并跳过异类，直接佐证当前编译二进制的两项新语义。

**绑定限制：保留 ELF 与当前 `/proc/.../exe` 哈希相同，只证明二进制相同，不证明保留源重新编译后独立复现该 ELF。** 没有可用 DWARF source info（readelf 输出为空），没有独立重建/链接。下面源码精确 diff 是“当前恢复的生产源码候选”，有 ELF 符号/字符串及上述 NMS 机器码佐证；没有声称每一行源语义都由机器码独立证明。当前模型的 live context/瞬时活动模型也没有读取或推理查询。

## 冻结 decoder / native guard 与当前语义

冻结 0301 decoder SHA `bf268b78139e0489fe00ed5b7f0ef5e6a59fbc49d02b8424a6e5d63369e19700`、11102 字节；当前 main.cpp 中同边界连续 decoder (`sigmoidf` 至 `QMutex m_mutex` 前) SHA `1dd7a6b24a4f741e7f336d459f18badc73ca059104ba5800a0a1aebc2c89aa3a`、11382 字节。当前切片为 `current_retained_decoder.inc`；全部 decoder 内变化精确保存在 `decoder_diff.txt`，周边 native/inference/model/display 变化在 `main_vs_candidate.diff`。

| 集成语义 | 冻结/候选 | 当前保留生产源码；集成影响 |
|---|---|---|
| `m_nc` 与 head 配对 | 根据 `(H,W)` 和通道数与 `m_nc` 的距离配对；class 数取 min | decoder 内这两项未改，仍有相等距离不建 scale 的行为；model scan 新增 16 类 trafficlight、严格 class ID sidecar 检查，context 切换带入 nc/trafficlight/geometry。不能固定所有模型为 3 类 |
| DFL sigmoid | 第一 scale 的第一类最多 2000 cells；max>1.5 或 min<-0.5 决定 sigmoid | 非交通灯完全保留；交通灯强制 sigmoid，不能因为 sample logits 均落在启发式阈值内而关闭。3D fallback 的最多 1000 cells 启发式仍未变 |
| DFL bins | box 通道/4，接受 1..32；float softmax/max subtraction/epsilon | 源 decoder 内未变；候选 native 只支持其固定 box64/regmax16、cls3 和 80²/40²/20²。不能把当前通用 1..32 或交通灯 60×80/30×40/15×20 直接套入固定候选 |
| 筛选 / NMS | score-only sort；DFL 在 NMS 前 top300；跨类别抑制 | 非交通灯保留；交通灯取消 NMS 前裁剪，NMS 同类才抑制，最多最终 300。IoU>0.45、面积交集、1e-6 denominator、每 cell 仅最高 class 及分数排序仍相同 |
| DFL 几何 | `int stride=MODEL_W/sc.w`；候选固定 strides8/16/32 | `float stride=m_geometry.width/(float)sc.w`，x/y 共用按宽度所得 stride，支持矩形 grids；非整除宽度行为也不同，不能用高=宽缩放 |
| 输入 / remap | square640 原有 feed；旧 candidate 有自己的 square preparation | 当前 `networkRgbFrame` 按实际 640×640 或 640×480 geometry，640 高图中心裁剪 y=80..559；480 原图供 square 模型时上下填114。decode 后统一 `restoreCanonicalDetections` 加 `(640-height)/2` 至 y1/y2；640×480 加80、640×640 加0，不能漏加或重复加 |
| 非 DFL | e2e Nx6 / split / fused 和 xyxy 切换 | decoder 内未改；e2e 仍不追加 NMS，split/fused 仍用默认 class-agnostic NMS。lane 路径仍独立 |
| RKNN code path | 旧 native candidate opt-in，native want_float=0、guard/session/lease；fallback 每帧 query float attrs | 当前源码 runOnce 对全部 outputs `want_float=1`，用 context 内缓存的 outputAttrs，随后 decode/remap/release；没有 native integration。模型加载先 query input geometry 和所有 output attrs；交通灯要求 input H480 和 box64/cls16 三个指定矩形尺度 |
| 输入 INT8 override | 环境存在时原对照路径；native guard 拒绝 override | 当前 `!m_trafficlight && DET_INT8_IN is set`，交通灯始终 RGB UINT8 NHWC；字节数由 geometry 计算。未来不能绕过这一交通灯约束 |
| model scan / driving | 旧扫描与显示/跟踪逻辑 | 增加 `/root/npu/trafficlight`、16个稳定 IDs、名字 sidecar、trafficlight 选择、driving-demo 默认轮换及 overlay；旧 native main 不能整体替换此 main，否则会丢掉新特性 |

当前 rotation 的两个模型文件已取回：

* `/root/npu/trafficlight/det-yolov8n-trafficlight-16cls-640x480-rk3568-raw-dfl6-int8.rknn` SHA `f96e09dd23c4edf9345e98e175284388c367d0ac3dcb144be417969a88ee233f`，4268313 字节；names/preprocess JSON 同时保留。
* `/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn` SHA `21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`，1870829 字节。

旧 native guard 仅允许 SHA `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9` 的 `/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn`（也已取回，4142230 字节）。还要求 `DET_V8_NATIVE=1`、一条 canonical mapped runtime、固定 runtime/API/driver、1输入6输出、3类非lane、无 INT8 override，以及输入 NHWC `[1,640,640,3]` INT8 zp -128/scale bits `0x3b808081`，所有六输出的名称、类型、quantization、stride、allocation bytes 精确一致。六输出 bytes 为 `[409600,102400,30720,51200,12800,3840]`，scale bits 为 `[0x3da0a0a1,0x3d9e27da,0x3d7c33af,0x3d425e3c,0x3d50337b,0x3d4d63f2]`，zp 为 `[0,-2,-35,83,69,71]`；原 guard 已在本目录冻结。

因此**当前命令行两个 rotation 模型都应走 float fallback**，旧 guard 不为它们提供 native 覆盖。当前保持 runtime 版本不等于当前模型/decoder 已被旧 120 cases 认证；本审计没有扩张认证范围。

## 后续最小补丁（本阶段没有实施、构建或部署）

1. 从本次恢复的 driving-demo 源树准备新隔离候选；保留 trafficlight 元数据/自测、geometry、DrivingDemo/overlay、当前 Makefile SOURCES 与推理属性缓存，不复制旧候选 main 覆盖当前 main。
2. 仅为固定旧 wb_v8 模型加入每 context native Session/guard。额外显式要求非trafficlight、geometry640×640、3类非lane、无 INT8 override；继续固定 model/runtime/API/driver/attrs。当前 trafficlight 与 wb_v4 必须保持原 float path。
3. 在当前 runOnce 的 outputs_get/decode/release 边界插入 opt-in/native 输出转换及 exactly-once lease；维持现有 networkRgbFrame 和最终 canonical remap（执行一次），保持当前 float fallback 及 cached attrs。不能直接套用旧 candidate 的整段 input preparation 或 query loop。
4. 以本次恢复 decoder 而非 frozen0301 作为新的 float oracle，分别验证非trafficlight 固定模型、trafficlight forced sigmoid/class-aware post-NMS300、rectangular crop/remap 和 rotation context 隔离；另做独立源码构建/链接绑定。后续运行或部署需由父任务定义新的执行边界，本审计没有执行这些动作。

本地 `verify.py` 已通过快照一致性、无扫描错误、全部下载哈希和 proc/disk/retained ELF 一致性检查（`verification.json`）。本目录所有脚本均只读取板端普通文件/proc/sysfs，`board_ssh.py` 仅使用 connect/run/open_sftp/get；没有 put、远端文件写入、设备 open、ioctl、mmap、reset、viewer/NPU 执行、停止或 FPGA/PDS 操作。Hindsight 服务连接失败，结论来自直接文件与板端证据。
