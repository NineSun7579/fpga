# 当前 RK viewer 构建来源只读审查 04

结论：**找到部署 ELF 的字节一致构建目录副本及最后增量构建命令；尚无可复现 ELF→完整源码绑定，不能给出 PASS。**

本次仅以 `project/tools/board_host.py:ssh_connect` 的 linaro 身份读取普通文件、构建工具版本及 Git 对象。新增内容仅此报告及 `viewer_build_provenance04/` 原始证据。没有重构建、部署、启动 viewer、打开 `/dev`、访问 DMA/BAR/PCIe config、reset/reboot/PDS 或创建新 device；BME disabled/0402 是任务提供的限制，本次未重新读取硬件确认。模型语义保持 `trafficlight-16cls,wb_v4_combo`。知识页连接失败后转为读代码。

## 已核实的来源链

| 对象 | 当前只读证据 | 能证明的范围 |
|---|---|---|
| 部署 ELF `/userdata/detview-driving-demo/detview-driving-demo` | 1197608 bytes，SHA256 `72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703` | 与冻结 03 身份一致 |
| 构建目录产物 `/userdata/linaro/detview-driving-demo-src/detview` | 相同大小、相同 SHA256、相同 Build ID | 构建目录产物与部署文件字节相同；并非只靠同目录源码推断 |
| 两份 ELF `.note.gnu.build-id` | `f0c69dc548b7add48099682d79b3514b34d34431` | 两份 ELF 身份一致；Build ID 不是源码摘要 |
| 部署前备份 `detview-driving-demo.before-ready-video` | SHA256 `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4`，1197400 bytes | 是另一份 ELF，不能替代当前身份 |
| 当前 `main.cpp` | 231296 bytes，SHA256 `a3865cd8e1c76d20c4f6df161334784c4a1d64f64366859549f41ccd670f08e9` | 当前源码身份与 03 一致；不是编译时输入 receipt |
| `ready_video_build.log` | 原始 2975 bytes，包含 moc、main.cpp、driving_overlay.cpp 的编译及 17 个 `.o` 的完整链接命令 | 明确的最后增量构建线索；没有产物 SHA256、输入摘要或构建退出状态 |
| `Makefile` + `detview.pro` | qmake 3.1 / Qt 5.15.8，`qmake -o Makefile detview.pro` | 当前 viewer 使用 qmake，不应拿 `stereo_demo/CMakeLists.txt` 或其他工程的 CMakeCache 当来源 |

原始证据：`viewer_build_provenance04/detail_readonly04_00.stdout.txt`、`remote_readonly04_02.stdout.txt`、`remote_readonly04_03.stdout.txt`，以及下载的 `source04__detview`、`deploy04__detview-driving-demo`、`source04__ready_video_build.log`、`source04__Makefile`、`source04__detview.pro`。

文件时间线（板上 UTC）：main.cpp / driving_overlay.cpp 为 2026-10-06 07:07:39，main.moc 为 07:07:42，driving_overlay.o 为 07:07:53，main.o 与 ready_video_build.log 为 07:09:06，构建目录 detview 为 07:09:08，部署 ELF 为 07:10:17。这支持“最后增量构建后复制部署”的解释，但时间戳和两个相同文件不能证明复制方向、执行者或实际部署命令。**本次 receipt 是现在的采集凭证，不是当时的部署 receipt。**

ELF 有 `.symtab` / `.strtab`，无 `.debug_*` 源码调试段；`.comment` 为 `GCC: (Debian 12.2.0-14) 12.2.0`。动态 NEEDED 包括 librknnrt、OpenCV calib3d/imgproc/core、Qt5 Widgets/Gui/Core、libstdc++/libm/libgcc_s/libc；完整链接输入比 NEEDED 多，不能只用 NEEDED 重建。

任务给定实际 argv：

```text
/userdata/detview-driving-demo/detview-driving-demo --driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo
```

本次 `/proc/*/cmdline` 只读扫描未找到此部署路径的进程（`detail_readonly04_03.stdout.txt` 为 `[]`），所以不声称本次重新确认运行 argv。03 `capture_viewer_recovery_identity.py` 只采集 ELF/模型哈希与桌面进程环境路径，不记录编译/部署来源，而且模型读取曾是 PermissionError；未重跑此脚本，以免覆盖冻结 03。

## Git 线索不等于当前源码

只读检视已有归档脚本，未执行它们，也未 fetch/push。`extra04__archive_driving_demo.sh` 指向 `feat/hdmi-driving-demo-20261005`、`RK3568/detview_tdm`，其内容是源码归档/文档/截图提交，不是当前 72cd ELF 的部署 receipt。

已有 `/userdata/linaro/driving-demo-archive-worktree` HEAD 是 `e431aacf77f4399bc6c20eeb9fc23ef0505410fb`（2026-10-05），其中 main.cpp SHA256 为 `1fb152cf8a5c964528bd9fea2d3a84ba0cf393a9848a98a84be65921a56e2a39`，正好等于 03 diff 的 historical_sha256，**不同于当前 a3865 源码**。已有 `/userdata/linaro/projects/fpga` HEAD 是 `687953518007a46b069d4cf42c7786e6fba0b21d`，main.cpp SHA256 `f91893ec34c014eb4f14a9631dc2ed4d2c248eb69a9e4411b307a05d3261516f`，也不同。

证据：`git_tool_readonly04.stdout.json`、`archive_git_readonly04.stdout.json`。归档 worktree 初次 Git 读因所有权检查失败，后续仅以单命令 `git -c safe.directory=<该路径>` 读取，`GIT_OPTIONAL_LOCKS=0`；没有写 Git config，也没有 checkout。没有声称上述 HEAD 是当前 ELF 的源码提交。

## 具体缺失

1. 缺少编译发生时完整 `.cpp/.h/.pro`、生成 moc、17 个链接 `.o`、工具链、头文件/sysroot、所有链接库的摘要清单。
2. 最后日志只重编 `main.o` 与 `driving_overlay.o`，复用了多个 10-04 / 10-05 的对象；当前相邻源文件不证明旧对象使用了当前源文件。本次保存这些对象仅供后续检查。
3. 缺少含当前 ELF SHA256、完整输入 manifest、构建退出码的历史 build receipt，也未找到含源/目标摘要及复制命令的历史 deployment receipt。
4. 尚未在隔离环境执行完整源码构建或对象链接复现；因此既没有 SHA256 相同的复现结果，也没有差异诊断。
5. 本次保存了当前源码/对象/日志及主要工具和库的哈希，但未归档完整系统头文件、CRT、libstdc++、链接脚本和全部传递依赖/sysroot；不能把这份采集包装成完整可复现构建包。

只读查找限定为 deploy/src 深度 5、`/userdata` 构建/receipt 名称深度 4、两个已知 Git 目录；有权限拒绝，完整 stderr 保留。结论是“本次范围内未找到”，不是全盘证明不存在。

## 下一步隔离构建输入与命令（本次未执行）

在**板外、无设备映射、离线 ARM64 Linux 构建环境**中准备与原记录一致的工具链/sysroot，再执行下面命令。不要在 RK 当前源/部署目录执行，也不要运行生成的 detview。此处不提供虚构镜像 digest：完整 sysroot/镜像仍是待补输入。

版本要求：GCC/G++ 12.2.0-14，binutils 2.40-2，GNU Make 4.3，qmake 3.1 / Qt 5.15.8（qt5-qmake 与 qtbase5-dev `5.15.8+dfsg-11+deb12u3`），OpenCV `4.6.0+dfsg-12`，保持原 qmake linux-g++ mkspec、头文件、CRT 和链接库搜索路径。

关键私有库：`/usr/lib/librknnrt.so` SHA256 `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`；`/usr/lib/aarch64-linux-gnu/librga.so.2.1.0` SHA256 `ba8744397f126c87dc2d637ddea35cca562aa8f323631bb4b9883816b3dcb714`。不存在 `/usr/lib/aarch64-linux-gnu/librknnrt.so`，不可误填为该路径。其余 OpenCV/Qt 库、qmake/moc/g++/ld 哈希见 `detail_readonly04_02.stdout.txt`，cc1plus/collect2 见 `git_tool_readonly04.stdout.json`；GL/pthread 见 `inputs_readonly04.stdout.txt`。这都是**当前**系统哈希，不证明历史未变。

先将本次 artifact 目录原样传入隔离环境 `/review04/artifacts`。以下还原命令验证 receipt 摘要，只恢复源码/头文件/pro，避免复用历史对象或生成文件：

```bash
mkdir -p /review04/src /review04/build
python3 - <<'PY'
import hashlib, json
from pathlib import Path
a = Path('/review04/artifacts')
root = Path('/review04/src')
prefix = '/userdata/linaro/detview-driving-demo-src/'
for receipt in ['detail_receipt04.json', 'inputs_receipt04.json']:
    for row in json.loads((a / receipt).read_text())['sftp_readonly_files']:
        remote = row['remote']
        if not remote.startswith(prefix):
            continue
        relative = remote[len(prefix):]
        if not relative.endswith(('.cpp', '.h', '.pro')):
            continue
        if relative.startswith('moc_'):
            continue
        data = (a / row['local']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256'], relative
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
PY
cd /review04/build
/usr/lib/qt5/bin/qmake -o Makefile /review04/src/detview.pro
make -j1 > /review04/build04.log 2>&1
sha256sum detview > /review04/elf_sha25604.txt
readelf -n detview > /review04/elf_notes04.txt
cmp /review04/artifacts/deploy04__detview-driving-demo detview
```

只恢复 `.cpp/.h/.pro` 会包含源码目录本来已有的 selftest 翻译单元：它们是历史链接输入，不能删去；这些命令不执行 selftest 或 viewer。编译参数应核对为 `-pipe -O2 -std=gnu++1z -Wall -Wextra -D_REENTRANT -fPIC`，宏为 `QT_NO_DEBUG,QT_WIDGETS_LIB,QT_GUI_LIB,QT_CORE_LIB`，链接为 `g++ -Wl,-O1`。

准确链接对象顺序：`main.o vision_pipeline.o vision_pipeline_selftest.o template_tracker.o template_tracker_selftest.o stereo_depth.o camera_dma_selftest.o frame_metrics_selftest.o calibration_capture.o hdmi_view_selftest.o inference_geometry_selftest.o driving_demo.o driving_demo_selftest.o driving_overlay.o driving_overlay_validation.o moc_vision_pipeline.o moc_calibration_capture.o`。完整 `-l` 库列表和 Qt 绝对库路径直接取原始 `source04__ready_video_build.log` 最后一条 `g++ -Wl,-O1 -o detview ...`，不要用手写短列表替代；也可核对 `source04__Makefile` 的 OBJECTS/LIBS/INCPATH。

若要先复现旧对象链接，在另一个隔离目录还原 receipt 中全部 17 个 `.o` 后，执行该原始链接行并保存新产物 SHA256/Build ID；即使链接相同也只证明对象→ELF，不证明源码→对象。完整源码构建如不相同，应比较生成 moc、各对象、链接器/库/CRT 与路径相关字符串，不能修改模型、参数语义或判定阈值来凑结果。新目录路径可能影响生成代码或 `__FILE__`；必要时在隔离环境内复用原绝对源码路径进行第二次比对，不能在真实板上覆盖。

最终可复现 receipt 应包含：完整输入和 sysroot 摘要、实际 qmake/编译/链接命令、退出码、生成 ELF SHA256/Build ID 与部署 ELF 的逐字节比较结果；在这些结果真实存在之前，状态仍是未证明。

## 原始证据索引与校验

`viewer_build_provenance04/receipt04.json`：首轮命令、UTC、主机、退出码、stdout SHA256 与原始 stdout/stderr。

`detail_receipt04.json`：82 个 deploy/src 顶层普通文件的 SFTP 只读快照摘要，以及详细 ELF/构建日志/工具版本/依赖哈希/进程读取 receipt。快照文件名采用 `source04__`、`deploy04__`，原远端路径保存在 receipt。

`inputs_receipt04.json`：三个已有归档脚本及 stereo_depth.cpp/.h、stereo_pairing.h 原始文件，补齐当前 qmake 输入子目录；`git_tool_receipt04.json`、`archive_git_receipt04.json` 保存 Git 和工具哈希读取命令。上述脚本只保存内容，未执行。

`artifact_integrity04.json`：本地重新校验所有 SFTP 文件和命令 stdout 摘要、与 03 冻结 ELF/main 身份比较的结果。未新增框架或 tests。
