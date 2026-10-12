# Viewer 完整隔离源码构建 05

**本次完整源码构建成功，产物与当前部署 ELF 逐字节相同：qmake=0、make=0、cmp=0。已取得真实源码→当前部署 ELF 的复现证据。** 这不是恢复历史构建/部署 receipt，也不代表全部环境文件均有构建前后摘要。

唯一远端目录：`/userdata/linaro/fpga-goal-viewer-build05-e4caef44-80c3-46f2-887c-84a9a1be2060`。本地证据即本报告所在 `viewer_build05_e4caef44-80c3-46f2-887c-84a9a1be2060/`，未改冻结 03/04 或 consumer 文件。

## 实际构建与产物

本地先验证 04 receipt 的摘要，再以 SFTP `wx` 向新目录恢复 31 个 `.cpp/.h/.pro`；覆盖 `.pro` 的全部 29 个源码/头文件及本地 include。没有复制旧 `.o`、moc、生成 Makefile。仅执行一次完整构建，保持原 flags；selftest 翻译单元按原 SOURCES 编译，但未执行。

```text
cwd = <唯一远端目录>/src
/usr/lib/qt5/bin/qmake -o Makefile detview.pro
/usr/bin/make -j1
cmp /userdata/detview-driving-demo/detview-driving-demo <唯一远端目录>/src/detview
```

| 项目 | 实证结果 |
|---|---|
| qmake | 2026-10-07 00:16:42.618434 → 00:16:43.483742 UTC，退出码 0 |
| make | 00:16:43.485432 → 00:23:22.672195 UTC，退出码 0 |
| cmp | 00:23:25.178867 → 00:23:25.185855 UTC，退出码 0 |
| 实际编译/链接 | 17 条 `g++ -c`，1 条原参数链接命令 |
| 新 ELF/部署 ELF | 均 1197608 bytes |
| 两份 ELF SHA256 | `72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703` |
| 两份 ELF Build ID | `f0c69dc548b7add48099682d79b3514b34d34431` |
| 新旧对象及 moc | 17/17 个 `.o` 相同；main.moc、两份 moc cpp、moc_predefs.h 全部相同 |

原始 argv、UTC、退出码及 stdout/stderr 索引在 `operations05.json`；原始命令见 `actual_compiler_link_commands05.json` 与 `make.stdout05.txt`。qmake/make 使用 strace 记录文件读取与 execve，没有添加 `-MD` 或修改功能 flags。

可 review 新产物：`generated05__detview`。对象/moc、生成 Makefile、nm/size、ELF sections/notes/dynamic 信息已保存；`artifact_comparison05.json` 给出逐对象、section 和函数大小比较。67 个原始下载 artifact 加最终审计文件的 68 项摘要校验均一致（`final_integrity05.json`）。

## 输入绑定与保留的缺口

31 个输入源码、工具链及真实 src/deploy/runscript 均开始/结束摘要相同。实际读取的 **695 个头文件、122 个库/CRT/链接输入**，开始/结束 SHA256 全部相同；工具包括 qmake、moc、G++、ld、cc1plus、collect2、as、make、pkg-config、strace。当前 main.cpp 保持 `a3865cd8e1c76d20c4f6df161334784c4a1d64f64366859549f41ccd670f08e9`。

| 输入/结果 | 回执 |
|---|---|
| 04 恢复来源及源码开始/结束摘要 | `source_upload_receipt05.json`、`source_begin05.json`、`source_end05.json` |
| 工具开始/结束摘要和版本 | `tools_begin05.json`、`tools_end05.json`、各 version/query/packages stdout/stderr |
| 构建前系统候选文件摘要 | `system_before05.json`，15832 个普通文件 |
| 实际头文件 SHA256 | `header_manifest05.json` |
| 实际库/CRT/链接输入 SHA256 | `library_linker_manifest05.json` |
| .pro/qmake feature/配置/pkg-config 读取 | `qmake_pro_dependencies05.json`，82 项，包含下述 3 个缺少开始摘要的 loader 配置 |
| 实际系统调用与最终文件审计 | `qmake.strace05.txt`、`make.strace05.txt`、`actual_read_inputs_final05.json` |
| 生成文件摘要和新 ELF | `generated_manifest05.json`、`generated05__detview` |
| 最终摘要/证据绑定索引 | `build_binding_summary05.json`、`source_to_elf_binding05.json` |

最终审计重组 105 条分段 syscall，未解析记录为 0，追踪了各 PID 的成功 chdir（src 或 Qt features）。第一次保守审计因存在 chdir 标记未验证；修正路径解析后的只读审计返回 0。原审计和摘要保存在 `actual_read_inputs_initial05.json`、`build_binding_summary_initial05.json`，最终以 `audit_trace_cwd.receipt05.json` 及 final 文件为准，未重新构建。

仍有 9 个实际环境读取文件**仅有结束摘要，没有构建前摘要**：`/etc/ld.so.conf.d/{00-aarch64-mali,aarch64-linux-gnu,libc}.conf`、`/etc/localtime`、`/usr/lib/locale/locale-archive`、`/usr/share/locale/locale.alias`、`/usr/share/locale/zh_CN/LC_MESSAGES/{gas,ld,opcodes}.mo`。没有用事后摘要伪补构建前证据；因此 `all_external_inputs_have_begin_end_hash=false`。这些缺口不改变已经实测的源码完整构建、全部实际头文件/链接输入摘要与 ELF 字节复现结果，但不得称为所有环境输入闭合或历史 receipt 完整。

## 边界与后续使用

没有运行 viewer/selftest、替换部署、改模型/driver、执行 DMA/BAR/PCI reset/BME/reboot/PDS。构建工具追踪只出现 `/dev/null` 标准输出丢弃路径，硬件设备打开路径为空。实际执行审计与日志已保存，不隐瞒该标准工具行为。

两份远端 `run_driving_demo.sh` 的开始/结束 SHA256 均为 `b38db583e900f8a095d1c9e1985c44d8d181c2908bf5326932e67d9a6bcc5108`；源/部署保护摘要见 `protected_begin05.json`、`protected_end05.json`。任务实际 argv 保持：

```text
/userdata/detview-driving-demo/detview-driving-demo --driving-demo --fullscreen --no-tracking --rotate-model trafficlight-16cls,wb_v4_combo
```

源码未修改，模型、driving demo、显示六路 motion/RAW 语义保持原内容；本次不声称重新运行验证其行为。新 ELF 已可作为后续 viewer 操作的已复现来源证据，部署/启动/截图仍由主任务另行推进，本次未执行。
