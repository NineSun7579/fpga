# Independent viewer source/build binding evidence

The recovered authored sources independently reproduce the installed viewer **byte for byte**. The isolated fresh build returned 0; all 12 new objects, all five checked qmake/moc generated files, and the 1,051,856-byte executable equal their frozen references. Local verification used both SHA-256 and direct byte comparison.

Executable SHA-256: `0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`.
GNU build ID: `06e86a07c8255efcd2aa12afe105b618967f8c15`.
Source/build binding status: `exact_executable_reproduction`.

The remote build root is `/userdata/linaro/fpga_v8_viewer_binding_20261005`. Its candidate executable is `detview`; the downloaded independent executable is `rebuilt/detview`. These are baseline candidates for the parent's next separate V8 integration work. This task adds no decoder feature and performs no deployment.

The original `/userdata/linaro/detview-hdmifull-src` directory and local `../viewer_build_recovered/inputs` were read only. All 61 entries were rehashed against the recovered manifest before building, and rechecked afterward. The installed `/userdata/detview-hdmifull/detview-hdmifull` hash remained unchanged. No recovered object, executable, Makefile, qmake stash, or moc product was reused in the build. SFTP uploaded 26 authored `.cpp`, `.h`, and `.pro` files, including the frozen local `rknn_api.h`. Fresh qmake/moc generated everything else.

Fresh commands were:

```sh
/usr/lib/qt5/bin/qmake -o Makefile detview.pro
make -j2 CXX='g++ -MD' LINK='g++ -Wl,-t'
```

The original qmake compiler/link flags were preserved: `-pipe -O2 -std=gnu++1z -Wall -Wextra -D_REENTRANT -fPIC`, original Qt defines/includes, and linker `-Wl,-O1` with the original library ordering. `-MD` records headers and `-Wl,-t` prints linker inputs; neither changed output bytes, as demonstrated by exact equality. `local_verification.json` compares every relevant fresh Makefile flag with the frozen Makefile. Generated qmake stash and moc file bytes also match despite the different build path.

Recorded toolchain: qmake 3.1 / Qt 5.15.8; GCC/G++ 12.2.0 (Debian 12.2.0-14); GNU binutils 2.40; OpenCV 4.6.0. Version outputs, specs, search paths, allowed compilation environment variables, and compiler/backend/tool hashes are saved. No credential values were printed or ingested; connections use `board_ssh.connect()`.

| Evidence | Content |
|---|---|
| `state.json`, `binary_comparison.json`, `local_verification.json` | Binding verdict, all object hashes, direct byte equality, fresh flags and generated-file equality |
| `frozen_local_recheck.json`, `original_remote_before.json`, `original_remote_after.json` | Frozen and board file identities |
| `commands.txt`, `qmake.log`, `compile_link.log`, `Makefile.fresh` | Actual full fresh compile/moc/link commands and link trace |
| `toolchain_versions.json`, `build_environment.json` | Tool versions/configuration and safe environment allow-list |
| `compiler_dependencies_by_unit.json`, `*.d` | All actual source/system/SDK headers read by each compiler invocation |
| `dependency_snapshots.tar.gz` | Exact bytes for 673 compiler dependencies, 34 compiler/tools/runtime files, 76 actual system linker inputs, and 45 candidate loader libraries |
| `supplement_snapshots.tar.gz` | 80 qmake/pkg-config/config inputs and 93 libraries already mapped by the live viewer |
| `*_snapshot_manifest.json`, `*_archive_identity.json` | Absolute source paths, resolved paths, file sizes, source symlinks, and SHA-256 identities |
| `elf_*.txt`, `candidate_runtime_ldd.json` | ELF sections, notes, dynamic dependencies, symbols/disassembly, candidate loader resolution |
| `process_guard_*.json`, `live_runtime_library_audit.json` | Read-only boot/process/executable/maps/fd evidence and hashes of actual mapped libraries |

Both downloaded archives and all 1,001 manifest entries inside them were locally verified. Snapshot files preserve bytes from symlink targets; original symlink/resolved paths remain in their manifests. Linker trace includes libraries later dropped by `--as-needed`, startup objects, archives, and linker scripts. Relative application linker objects are preserved separately in `rebuilt/`. The 45-library candidate `ldd` set differs from the live process's 93 mapped libraries because the live Qt desktop session has loaded plugins; both sets are frozen separately. Running `ldd` inspected loader resolution and did not enter the application's main routine.

`librknnrt.so` actually resolved at link/load to `/usr/lib/librknnrt.so`, SHA-256 `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885`. The live mapped copy matches. Linker input `librga.so` resolves to `/usr/lib/aarch64-linux-gnu/librga.so.2.1.0`, SHA-256 `ba8744397f126c87dc2d637ddea35cca562aa8f323631bb4b9883816b3dcb714`; this executable has no `DT_NEEDED` entry for librga and the audited live process has no librga mapping. The RKNN runtime shared library is a dependency, not the viewer source.

The parent-reported PID `136782`, start tick `24241761`, was already absent at this subagent's accessible process audit. The live installed viewer was PID `139571`, start tick `24603902`, on boot `d167174d-777b-4f93-bc1d-ea01ffc83a9a`; that identity and its executable remained unchanged through collection and the final audit. The initial unprivileged `/proc` audit could not read the root-owned viewer and is retained separately; an elevated **read-only** guard corrected that gap while the build was underway. Consequently the process evidence covers the accessible audits, not an uninterrupted claim starting at the parent's earlier PID. No process start/stop/signal, viewer invocation, driver open, GUI action, NPU test, PDS operation, or installation occurred.

Exact output establishes that these recovered sources, compiled in the frozen environment, produce the installed program logic. It does not establish the historical provenance of the old build, external kernel-driver allocation ownership, active FPGA register/DDR contents, or V8 integration correctness. Those are separate claims.
