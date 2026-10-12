# 独立 cooperative paired benchmark

所有新增文件仅在本目录。未修改 RTL、Viewer、Linux transport 或已有 host helper；未打开驱动、板卡 GUI，未执行板端/NPU/PDS。`platform_unbound.cpp` 默认在 RKNN 初始化和 ARM 之前拒绝运行，不提供自动初始化或伪造平台预留。

## 可立即执行的离板验证

Windows：`build_fake.cmd`，使用 MSVC C++17 `/W4 /WX`，只编译/执行 fake。

Linux：

```sh
cmake -S . -B artifacts/fake
cmake --build artifacts/fake
ctest --test-dir artifacts/fake --output-on-failure
```

fake 报告 `acceptance:false`、FPS 为 null；毫秒值仅用于编排回归，不是硬件性能。故障用例验证不完整 DMA 不 ACK、不确定 ACK 不重试且保留完整 CPU bytes、状态 bit2/reset 中止、错误源身份/字节拒绝、短毫秒 sleep 的有界轮询，以及 get/release 错误不形成完成计数。

## 平台接入和 RK3568 编译（本次未执行）

`platform_binding.hpp` 中 `bind_platform(receipt,generation)` 是唯一委托入口，返回 `Binding.owner`（`PlatformOwner`，拥有实际 fd/maps/controller lock 和 Transport）、共享操作锁、两个 helper 的配置/外部预留和 ARM 凭据。后续在本目录添加 delegate，通过 `PAIRED_PLATFORM_BINDING` 选择它。可委托正在开发的 `cooperative_linux_transport`，不依赖它尚未确定的类名，也不修改其文件。factory 只能在取得任何硬件资源之前抛异常；取得资源后即便拒绝激活，也必须返回仍持有资源的 owner，交由退出策略处置。

delegate 必须保持真实的 authoritative transport mutex、exclusive controller ownership、control scratch、互不重叠的 RAW/output RX 槽位以及 reset/lease 外部恢复纪律。Transport 阻塞调用自身必须有有界单事务/整 DMA 超时；本工具的 steady_clock deadline 无法抢占一个不返回的虚函数。CLI 在任何 ARM/RKNN 初始化之前要求 provider 返回真实 controller session、已完成的有界 driver 验证记录、事务 deadline 契约和持久 owner 契约；没有这些记录就拒绝激活。非空记录标识只是 provider 证据引用，不能把任意 CLI 字符串、未经验证的 ioctl 超时假设或制造的 boolean 当成验证。helper 的有限读写组通过一次 RAW 或一次 output public operation 执行，所有 output public operations 再包共享 coordinator；RAW helper 已自行获得同一非递归锁。

ARM 只接受外部分配且已持久化的新非零 generation 和已静止的 host/cooperative/DMA 凭据。工具不读旧 generation 后自行加一，不 reset，不重试 ARM/ACK，不以重新构造对象恢复 lease。失败只有在无硬件 owner，或 helper 没有不确定 lease 且 provider 给出经验证的退休空闲凭据时才能返回并释放资源。硬件/lease 不确定或缺少凭据时，必须保持进程和 owner 存活，绝不能以退出进程代替恢复：驱动全局 release 可能释放仍在使用的 DMA 映射。

### provider 生命周期接口（下一阶段绑定点）

在本目录实现 `PlatformOwner::transport()`、`activation_evidence()`、`retired_idle_receipt()`、`quarantine(reason)`、`authorized_recovery_receipt()`。`retired_idle_receipt` 只读取 authoritative 已退休 DMA、transport 和 lease 的状态记录，不发硬件 I/O；任一状态不确定就返回空。receipt 包含原 controller session、原 generation、实际证据记录引用和 `ExitAuthority`，不能用仅布尔的“idle”代替记录。`quarantine` 为 noexcept 的永久隔离 latch，不 ACK/reset/retry/close/unmap，也不释放 controller ownership；即使报告写入失败也保持 owner。`authorized_recovery_receipt` 是有限、无硬件操作的外部授权恢复记录入口；delegate 必须先验证外部物理静止/恢复证据，再返回 `ExternalPhysicalRecovery` 类型、匹配本 session/generation 的 receipt。普通 idle receipt、错误 session/generation、空证据、信号或经过的时间都不能解除隔离。

CLI 在 bind 前安装 Linux 持久 `sigaction`（INT/TERM/HUP/QUIT），handler 只记录请求；在 ARM/采集边界停止新作业。异常不会展开 owner/Receiver/Runner。隔离 latch 后以 QtCore `QSaveFile` 原子 commit `failure.json`（不允许 direct-write fallback），然后保持前台，50ms sleep 的有限循环只等待已授权外部恢复 receipt。收到终止信号只打印一次“拒绝退出，需要物理恢复”的决定；不会因此析构或关闭映射。收到正确的外部物理恢复 receipt 后，才允许以失败状态释放 owner 并退出。报告写入失败也不能退出。正常完成发布报告之前同样必须取得安全空闲凭据。

无法保证进程在 SIGKILL、操作系统强制终止、掉电或故障后存活；操作员必须先在进程外完成物理静止/恢复，再终止进程。Windows fake 只验证可处理的 CRT 信号，不证明 Windows 控制台强制关闭的行为。默认 unbound delegate 在任何硬件获取前拒绝运行，没有持久 holder/provider 时不允许 CLI 激活。

固定契约：六路摄像头集成中的 C5（camera=4）未滤波 little-endian RGB565，640×480；RAW 地址 0x01800000/0x01a00000，prepared 地址 0x08000000/0x08200000。RGB888 使用位复制扩展、不缩放，640×640，上下各80行填114。Camera 到物理线路的确认来自 delegate 外部凭据。两个 helpers 共用 `SessionFaultTransport(backend,0x40010410)`，即实际 RAW STATUS bit2；这不是 output STATUS 或本地偏移。独立 RAW/output claim 有限 poll pass，steady_clock deadline，未就绪 sleep 2ms。copy 到预分配 owned vector 后各自立即 ACK，最后以 `paired_input_guard` 校验 source bank/address、sequence、generation、camera、token 和 RGB 逐字节一致；重复/回退 sequence 拒绝。

```sh
cmake -S . -B artifacts/rk3568 \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/rk3568-toolchain.cmake \
  -DPAIRED_BUILD_RKNN=ON \
  -DRKNN_RUNTIME=/path/to/rk3568/librknnrt.so \
  -DPAIRED_PLATFORM_BINDING=/absolute/path/to/this/directory/platform_delegate.cpp \
  -DCMAKE_PREFIX_PATH=/path/to/rk3568/Qt
cmake --build artifacts/rk3568
# 仅在之后明确授权板端实验且平台绑定完成后运行：
./artifacts/rk3568/paired_bench /path/to/pinned-model.rknn external-receipt persisted-generation output-dir
```

只依赖 QtCore、标准 C++17 和 RKNN runtime；不依赖 QtGui、OpenCV 或完整 Viewer。使用保留的 SDK header 和 current decoder `.inc`，当前 decoder 的 square geometry.width=640、canonicalTop=0，不给检测坐标额外加80。RKNN 初始化 flags=0，缓存 input/output attrs 一次，经 `check_current_profile` 验证 pinned model/runtime 实际 SHA256、唯一实际 `/proc/self/maps` runtime、API/driver、输入和全部六个 head 的类型/shape/stride/量化。拒绝 `DET_INT8_IN`，输入仍是 UINT8/NHWC/pass_through=0。baseline 是真实 want_float=1/current retained decoder；candidate 是 want_float=0/current native profile。每个作业包含 inputs_set→blocking run→get/尺寸验证→decode/owned检测结果→release，release 成功才返回完成；异常时成功 get 的 output 只 release 一次，release 不确定不重试。

## 计时与验收

先完成30个 warm pair（不计时），再240个同物理 RAW 的正确性 pair。次序 AB、BA 交替；两条 profile 各有实际 processing interval 和从同一 capture start 到完成的绝对 response。第二条 response 包含前一条执行等待，明确保留该次序影响。共享 acquisition 每个 pair 只发生一次，`paired_sustained_fps:null`，不以两个推理结果制造两个独立输入帧或 pipeline FPS。

之后4轮 ABBA 独立窗口，每个窗口30个新作业，共每 profile 240个 timed completions。每个窗口仅执行指定 profile，每个作业真实 acquire 两条 lease、RAW owned copy/ACK、prepared owned copy/ACK、byte certification、RAW inventory copy、必要的 CPU prepare、RKNN 完整完成及 storage recycle。整窗口 steady_clock wall 和完成数得到 observed completed FPS，包含所有上述成本；不把 stage sum 当 wall time。baseline 也运行 FPGA convert/搬运/校验，这衡量固定 cooperative 双消费和校验策略下的作业响应，不能声称独立纯CPU部署或取消 RAW-copy 策略后的收益。

完整 byte certification 和 inventory copy 成本显式计入两条 timed profile。candidate RAW 接收 overhead 没有隐去。`samples.csv` 单列 RAW/output copy+ACK、claim wait、certification、CPU prepare 和 RKNN 五阶段；`processing_ms` 不包括采集，`completion_from_capture_ms` 是实测绝对 interval。

每轮对 A0/B1、A3/B2 的 ordered RAW inventory **逐字节**比较，并比较 owned 检测结果（class、box≤1e-3像素、score≤1e-6，最大二分匹配）。同帧正确性与独立窗口都必须零误差、运行时 metadata pins 全通过、destroy 成功，才能 `acceptance:true`。这是比较证据有效的验收，不保证 candidate 更快。没有外部支持的确定性 source stream/replay 时，live camera 跨窗口 RAW 通常不同，工具返回失败且不接受性能结论；不会发明 H2F 帧注入或自行接管摄像头。跨窗口 source sequence 必须递增，payload 可以重复；同帧 pair 的源 key 必须完全相同。

正确性 capture 导出 `.raw565`、`.rgb640`、descriptor/token 与 SHA256；timed inventory SHA256 在窗口结束后计算，真正的 equality 是 owned RAW byte 比较，非仅 hash。`report.json` 含 pinned model/runtime、完整 attrs、API/driver、各窗口 wall/completions；`samples.csv` 含源 key 和 stage timings。失败的原子 `failure.json` 为 acceptance=false/FPS=null，记录隔离决定、session/generation、lease 不确定性和保留 CPU bytes 的长度/完整性。安全空闲失败才立即返回非零；不确定失败保持前台，等外部物理恢复 receipt 后才返回非零，不输出部分失败窗口的成功 FPS。完整/部分 CPU bytes 在 Receiver 的 evidence 中保存至安全释放；没有隐式 ACK/恢复析构动作。baseline 的 FPGA copy 和认证成本仍包含在指标内。
