# Current native Qt candidate isolated build 02

Completed: build exit code 0. Product `rebuilt/detview-native-current-candidate` SHA256 is `8d8f4ebcbf856bc8657488b14525871d11ba67d4090e69df1aa2c8162e54ee84`, ELF build ID `cceb332f35fc434717d2723c71cfc802ed673dad`. All 17 objects were downloaded; 16 are byte-identical to the frozen current baseline and only `main.o` differs. All generated MOC files, predefinitions and qmake stash are byte-identical. ELF NEEDED entries and compiler comment match the baseline.

Selftests passed with exit code 0: DFL tests `(bins=16,nc=1)` and `(bins=8,nc=29)` each produce exactly one expected detection, box `(156,68,188,116)`, score `0.90`, class 0. Trafficlight dispatch passed 17 geometry checks and 12 decoder checks (29 `[ok]`, zero `[FAIL]`). Exact commands and diagnostics are preserved.

40 authored inputs were uploaded and hash-verified; 34 were confirmed by actual compiler dependencies. Remaining six are the unchanged `.pro` and five unused stereo-demo files listed in `source_object_counts.json`. Final snapshot counts: 34 toolchain files, 864 qmake/pkg-config files, 703 compiler inputs, 76 linker inputs, 45 candidate runtime libraries, 80 qmake configuration files and 93 libraries mapped by the existing viewers. All snapshot source hashes remained unchanged. Prepared candidate/frozen baseline/exact rebuild directories and original remote source directory remained unchanged.

Current boot `12803068-a3fb-4341-b05e-4f31921cfb1b`, viewer PID 2740/start ticks 152164 and image SHA256 `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4` remained bound. All-device-owner maps are preserved, but are not globally byte-identical: across selftests only SSH server PID 5503 heap grew; all 69 common owners retained identity/FDs and the viewer maps were unchanged. Across the longer build observation, polkit PID 1216 anonymous memory changed and the already-running viewer added two `/dev/mali0` mappings. Transient background/SSH owners were added/removed. `mapping_delta_analysis.json` records exact map diffs; no replacement or intervention was performed in response.

This directory owns only its build workflow, downloaded products and evidence. Prepared candidate, frozen current baseline and exact rebuild evidence are protected by `protected_before.json` and subsequent full-file inventories.

Remote stage: `/userdata/linaro/fpga_v8_viewer_binding_20261005_native_build_02_2597e95edba5`.

The original `detview.pro` is unchanged. The target override is `/usr/lib/qt5/bin/qmake -o Makefile detview.pro -after TARGET=detview-native-current-candidate`. Compilation uses `make -j2 CXX='g++ -MD' LINK='g++ -Wl,-t'`. Every object is rebuilt. No optimization, fast-math, CPU or type changes are introduced.

Uploaded authored inputs total 40: 35 original source/header/project files, three byte-identical old native headers and two new current native headers. Original `main.cpp` is the prepared candidate delta; every other original manifest hash is checked. `upload_verification.json` binds every uploaded byte. Not every uploaded source belongs to this target; `source_object_counts.json` lists compiler-confirmed inputs and the unused project/stereo files. The unchanged project produces 17 objects, including generated MOC units.

`qmake_flags_comparison.json`, `qmake_semantics.json` and `qmake_makefile_normalized.diff` record generated build settings. `generated_comparison.json` compares MOC outputs and qmake stash. `binary_comparison.json` compares all objects with frozen current objects. `elf_*` records ELF identity, sections, symbols, dependencies and disassembly. `compiled_authored_input_verification.json` binds authored headers/sources to actual GCC dependency files.

After normalizing stage paths and the target override, Makefile differences are cold-qmake `.qmake.stash` prerequisite lines and the five included native header dependencies on `main.moc`/`main.o`. Compilation recipes and semantic flags are unchanged.

Toolchain, qmake/pkg-config configuration, all actual compiler dependencies, traced linker inputs, candidate loader dependencies and libraries mapped by existing viewer processes are hashed and snapshotted. Archives are downloaded and their members verified. Header inventories and final hash checks detect changes during the build. `artifact_manifest.json` hashes the reviewable local artifact set, excluding itself.

Only `--dfl-selftest` and `--trafficlight-selftest` are eligible. Source dispatch returns before model scanning and normal viewer construction. Both instantiate only an unstarted `InferenceThread`; its constructor calls `QThread(parent)`, context starts at zero and native session pointer starts null. Tests use synthetic buffers and software QImages. Trafficlight dispatch includes `runInferenceGeometrySelfTest`; there is no standalone inference geometry flag. `QT_QPA_PLATFORM=offscreen` is set for QApplication; XDG runtime/cache/config directories are confined to the isolated remote stage. Exact argv, output, exit codes and diagnostic counts are in `selftest_results.json`.

Process guards preserve current boot/PID/image identity and existing viewer maps/FDs before and after. Separate all-device-owner inventories include all visible processes holding character device descriptors and their full maps; changes from external activity must be assessed against the saved records.

No GUI viewer launch, RKNN initialization, inference, FPGA/PDS work, device test, deployment, live process stop or replacement is performed. Synthetic tests validate the retained float decoder and geometry; compiling the native RAII path does not validate actual RKNN acquisition/release or its runtime performance. No FPS claim is made.

The first shell invocation rejected Windows CRLF before qmake or compilation. Only this directory's build script was normalized to LF and re-uploaded; `script_repair.json` records the repair. Prepared owner sources were never edited.
