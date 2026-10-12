# 当前驾驶演示 viewer 独立精确重建 02

本目录独立使用 `../current_viewer_binding_02/inputs/userdata/linaro/detview-driving-demo-src/` 的冻结源码，保留交通灯、推理几何、驾驶覆盖层和原始编译语义。目标 executable SHA-256 为 `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4`。

编译/链接返回码为 0；下载后 executable 和 17/17 个新对象均与冻结版本逐字节相同，18/18 个产物 ELF section 相同。91 个冻结下载文件保持原哈希，实际编译使用的 29 个作者编写的输入均匹配冻结源码。3 个依赖归档的 1,883 个 manifest 条目已逐项核验。最终结果由 `state.json`、`binary_comparison.json`、`archive_verification.json` 和 `artifact_manifest.json` 记录。

新远端 stage：`/userdata/linaro/fpga_v8_viewer_binding_20261005_current_rebuild_02_9af743d7dff0`。本目录和该 stage 是本任务唯一写入目标；原始冻结输入、安装路径、原始板端源码目录及既有构建证据不作为写入目标。

冻结 retrieval manifest 有 92 项，其中 91 项有本地下载文件；`/proc/2740/exe` 一项下载曾被拒绝，因此通过新鲜只读 sudo `/proc` 审计检查实际进程镜像。冻结文件逐项进行 SHA-256 和长度检查。原始 `.pro` 有 15 个作者编写的源文件，qmake 加入 2 个 MOC 编译单元，实际对象总数为 17。`main.moc` 被 `main.cpp` 包含，不是额外对象。

`rebuild.py` 复用并记录既有 `viewer_rebuild_evidence` 的 SSH、只读 `/proc` 审计、构建及依赖采集工作流，使用 `board_ssh.connect()`，不打印凭据。上传仅限 35 个原始 `.cpp/.h/.pro`，排除旧 `moc_*`；所有 Makefile、MOC、对象和 executable 均重新生成。

命令顺序：

```text
python project/fpga_v8_migration/current_viewer_rebuild_02/rebuild.py prepare
python project/fpga_v8_migration/current_viewer_rebuild_02/rebuild.py build
python project/fpga_v8_migration/current_viewer_rebuild_02/rebuild.py collect
python project/fpga_v8_migration/current_viewer_rebuild_02/rebuild.py supplement
python project/fpga_v8_migration/current_viewer_rebuild_02/rebuild.py finalize
```

`prepare` 拒绝复用既有 stage；后续阶段读取已记录 stage，不创建第二个目录。编译前要求 GCC 12.2.0 和 Qt 5.15.8。构建通过原 `.pro` 执行 qmake，然后执行 `make -j2 CXX='g++ -MD' LINK='g++ -Wl,-t'`。`-MD` 记录实际系统和 SDK 头依赖；`-Wl,-t` 记录链接输入，保留相对对象名和顺序。未添加路径映射、CPU/ASM 调整或优化猜测。

构建语义为原 Makefile 的 `-pipe -O2 -std=gnu++1z -Wall -Wextra -D_REENTRANT -fPIC`，原 Qt defines、include 路径、OpenCV pkg-config 展开及链接库。`qmake_flags_comparison.json` 比较原始和新生成设置；`qmake_makefile_normalized_comparison.json` 仅在证据比较时替换 stage 绝对路径，不改写任何构建输入。

5 个重新生成的 MOC/预定义/`.qmake.stash` 文件均逐字节相同。Makefile 在路径归一化后仅有 3 行 `.qmake.stash` 依赖登记差异：冻结 Makefile 生成时 stash 已存在，本次首次 qmake 冷生成时不存在。移除这些依赖登记行后完全相同；所有语义设置、对象顺序和构建规则均一致。完整差异保存在 `qmake_makefile_normalized.diff`。

证据包含所有对象与 executable 的逐字节比较、qmake/MOC 输出比较、源码/对象计数及顺序、实际编译输入哈希、工具链和运行依赖快照、pkg-config/qmake 配置快照、系统头依赖编译前后哈希、ELF NEEDED/build-id/.comment、实际活跃进程映射库，以及原始目录和进程身份前后检查。`state.json` 和 `artifact_manifest.json` 是最终结果入口。

任务仅编译和链接；viewer、GUI、自测、RKNN 初始化/推理均不执行；不打开驱动或设备，不停止或修改活跃 viewer，不调用 PDS。身份若发生外部变化，工作流保存 `external_change_stop.json`，在后续远端写入前停止；这不否定另外建立冻结源码绑定的可能性。
