build04 完整候选生产验证完成

状态：PASS_COMPILE_SYNTHESIS_EXPORT_INDEPENDENT60_ONLY
源741逐字节与build03一致；完整源树742文件（含原Python缓存）；186工程登记。build03完整树874文件哈希与文件集合均未改变。

compile PDS shell PID=34752 controller PID=71076
synthesize PDS shell PID=77588 controller PID=74952
compile_export PDS shell PID=32996 controller PID=74952
actual_export PDS shell PID=54240 controller PID=74952

compile和synthesis均60独立寄存器、28同步、32复位，全部语义检查PASS；C/P无CE采用官方精确模型。
失败日志与DB均保留。未运行mapping/PNR/bit/remote/program/Flash。下一阶段仍需主会话完整60位置约束。

实际工件最终哈希：
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\compile\v7_sdt_top_comp.adf
f49e150d01c754dccff81086dcf148fc46f4640d58492888ba09745498ef0ec4
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\synthesize\v7_sdt_top_syn.adf
f7547eb21bbaeaf61324eafb766c5bc63e130a68abcc40c1556bbf634fa32c5e
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\compile\cmr.db
840d2d0c8f5316c22efc9cd3ed47c5972d7eb67e790c16f246efb85fef6d7c1e
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\synthesize\snr.db
e176877f919379ad9b570a491667d9fc8ca46b3c904e88b921aee8f92c252742
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\compile\analysis\graph.json
8a5fd6e2d07c1de21fb62c341e2c933be63ac6c0c2f6d296cbbea816d092befa
C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\actual\analysis\graph.json
4fbef701a4220c5abc86f7b160ad158498bf2391a180dbd37bf6e89aae38fb96
