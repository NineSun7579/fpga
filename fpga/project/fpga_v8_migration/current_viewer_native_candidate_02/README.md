# 当前 driving-demo native 候选 02（仅本地源码准备）

基线为 `../current_viewer_binding_02/inputs/userdata/linaro/detview-driving-demo-src`。基线 executable SHA256：`f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4`；既有 `current_viewer_rebuild_02` 记录 executable 和 17/17 对象逐字节匹配。本候选没有编译完整 viewer，也没有运行 GUI、SSH、RKNN 初始化/NPU 推理、设备或 PDS。

`src/` 包含全部 35 个作者编写的 `.cpp/.h/.pro`，排除原 Makefile、MOC、对象、二进制等生成物。除 `main.cpp` 外，34 个原文件逐字节不变，包含 `.pro`、交通灯、geometry、driving demo、overlay 和原自测。旧候选的 `raw_dfl_native.h`、`viewer_native_guard.hpp`、`viewer_native_qt.hpp` 逐字节复制，未覆盖任何旧目录。新增 `current_native_gate.hpp` 和 `current_native_qt.hpp` 是当前门禁及缓存属性适配。

默认保留 float；仅 `DET_V8_NATIVE=1` 请求 native。当前额外门禁明确要求 `!trafficlight && width==640 && height==640 && channels==3`。仍只接受旧 pinned wb_v8 SHA256 `be7ee818...`、已映射唯一 runtime SHA256 `73993ed4...`、精确 API/driver、1 输入 6 输出、3 类、非 lane、无 `DET_INT8_IN` 环境覆盖，以及全部原记录 metadata/quantization/stride。即使同为三类、相同输出形状，也不会仅凭形状启用。没有扩展 profile。

当前轮换的 trafficlight 16 类 640×480 和 wb_v4_combo 保持原 float fallback；本候选针对旧 pinned wb_v8，不能加速当前活动轮换模型。没有 FPS 声明。

每个 cached context 拥有独立 Session/decoder/阈值/LUT；cache 使用 `std::vector`，只在 reload 时增长。reload 和退出时先清空 `m_nativeSession`、`m_outputAttrs`、`m_ctx`，再销毁 context；仅在增长结束后绑定当前条目。保留原选择顺序、geometry、class labels、generation/frameId、metrics 和完成/失败回报。门禁失败沿用已缓存 outputAttrs；适配器只补充 SDK version 查询，不重新查询输入或输出属性。

实际 `networkRgbFrame`、RGB feed/memcpy/INT8/input set/run 管线字节不变。当前 production decoder 整段与 `current_retained_decoder.inc` 字节相同，保持原 include 位置中的语义；oracle 测试直接导入该段。640-square profile 的 current `width/sc.w` 与冻结 stride 8/16/32 一致，canonicalTop 为 0。native 和原 float 都调用原 canonical restore。原 geometry 自测保持字节不变；本任务没有编造 geometry/remap 实现，也未执行需 Qt 的 geometry/trafficlight 自测。

成功 outputs_get 后立刻建立 OutputLease；显式 finish 或异常退出均只尝试一次 release。native buffer 校验、decode 或 release 失败返回 false，发生在 completed 计数之前，不再进行第二次推理。float 路径继续使用原 attrs/decoder 和 release 返回值处理方式。

本地验证命令：

```text
python project/fpga_v8_migration/current_viewer_native_candidate_02/run_tests.py
python project/fpga_v8_migration/current_viewer_native_candidate_02/audit.py
```

测试采用 MSVC C++17 `/W4 /WX /fp:precise /utf-8`，直接导入的生产 decoder 保留原隐式 int/float 转换，仅对该导入段抑制 C4244。测试覆盖记录 profile、逐头 metadata/type/quant/shape/stride 拒绝、伪装相同形状/重排头、额外 rectangular/trafficlight/RGB 门禁、旧 float/native context 切换中独立阈值及 LUT 状态、输出所有权与异常/错误释放恰好一次。oracle 使用实际当前 decoder 比较 pinned signed 三尺度输出的类别、顺序、分数和坐标，阈值 0.05/0.32/0.5/0.95；这是有限合成 fixture parity，未代表板端端到端验收。context 测试为纯 C++ cache/decoder 生命周期验证，未运行 Qt InferenceThread。

交接入口：`patch.diff`（原 main 最小差异）、`manifest.json`、`frozen_inputs_sha256.json`、`audit_results.json`、`artifacts/results.json` 和编译/测试日志。audit 核验原冻结输入及重建证据未改、34 原文件/3 旧 headers/production decoder/输入管线/完成回报尾段一致，并记录候选全部 src 哈希。

后续 agent 独立编译完整 viewer：使用此 `src/` 和原 `detview.pro`，在新的隔离构建目录生成 qmake/MOC/Makefile，沿用既有当前重建工具链及依赖；不要复制旧生成物。完整 viewer 编译、Qt geometry/trafficlight 自测及真实 runtime 集成验收尚未完成。本次授权仅本地准备，不包含部署或远端操作。
