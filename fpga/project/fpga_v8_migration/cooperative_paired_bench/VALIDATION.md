# 本次离板验证

- `cmd /c build_fake.cmd`：MSVC 19.44，C++17 `/O2 /EHsc /W4 /WX` 编译和运行通过，`fake cases passed=13`。
- CMake 3.30.2 + Ninja + GNU 13.1 C++17：配置、构建通过。`ctest --test-dir artifacts/cmake_fake --output-on-failure`：1/1 test passed（该 executable 内含13项用例）。
- GNU 13.1 + Qt 6.11.1 Core + 已保留 RKNN SDK headers：`main.cpp platform_unbound.cpp` 的 `-std=c++17 -Wall -Wextra -Werror -fsyntax-only` 通过。此前也成功编译 main.cpp 为 object。

13项用例：固定 RAW inventory 的 AB/BA 与 ABBA 完成计数；变化 RAW 序列拒绝比较验收；短 DMA 禁止 ACK；不确定 ACK 单次尝试且保留 owned bytes；实际 RAW STATUS bit2；错误 RGB 字节；错误源 sequence；有界 Busy 轮询；RAW copy 后 bit2 故障；get 失败零完成；release 失败零完成；缺少持久化 generation 授权零 I/O；RX owned storage 回收复用。

fake 输出 acceptance=false，所有 FPS 为 null。测试提供编排与错误处理证据，不提供 FPGA/RK3568 推理正确性或性能证据。

真实 runner 仅做源码编译检查：没有 RKNN runtime 链接/执行、板卡连接、驱动 open、GUI、NPU 或 PDS 操作。当前默认 binding 故意未连接平台；下一阶段必须提供有界实际 Transport 和外部 ownership/generation/布局凭据，再授权硬件实验。跨独立窗口 live RAW 不相同时，报告必须拒绝性能比较验收；本次没有获得或声称任何硬件 FPS。

## 失败退出策略修正验证

仅修改本目录文件。原13项 fake 回归保持通过，新增4项 lifecycle 用例通过：

- 缺少 idle receipt 拒绝退出；不确定 helper lease 不能被普通 idle receipt 覆盖。隔离 owner 始终存活，报告一次，重复终止请求只记录一次拒绝退出决定，等待期间零硬件写入、零重新构造/ARM。普通 idle、错误 session/generation、空物理恢复记录全部拒绝，只有匹配的 fake 外部物理恢复 receipt 才允许释放。
- 缺少有界 driver 测试记录或持久 owner 契约拒绝激活。
- 原子证据报告回调失败也不会异常展开隔离 owner。
- 两次实际 CRT SIGTERM raise 后进程仍继续执行；不声称 Windows 强制关闭或 SIGKILL 可被阻止。

MSVC `/W4 /WX` 构建执行：`fake cases passed=13`，`quarantine lifecycle cases passed=4`。更新后的 GNU/CMake fake 构建及 CTest 1/1 通过。QtCore + 保留 SDK 下 `main.cpp platform_unbound.cpp` 的 `-Wall -Wextra -Werror -fsyntax-only` 通过，更新后的完整 `main.cpp` 编译为 `artifacts/main_syntax.o` 也通过；未链接或执行 NPU runner。

Linux sigaction 路径、真实 driver 有界性、实际 quarantine owner 和外部恢复 receipt 验证尚需 Linux delegate/平台验证。本次 fake 是有限 pass 测试，未启动无限等待进程；`QSaveFile` 原子写入路径已编译检查，未声称做了文件系统崩溃/掉电测试。实际 CLI 在缺少 provider 时仍禁止激活。
