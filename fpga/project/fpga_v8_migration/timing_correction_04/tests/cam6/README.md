# 实际 cam6 隔离差分

运行：`python project/fpga_v8_migration/timing_correction_04/tests/cam6/run_cam6.py`。

候选为 `../../rtl/ov5640_ddr_tc04.v`。参考来自 V5
`inputs/source/ov5640/ov5640_ddr/ov5640_ddr.v`，不是 capture wrapper。
参考、三个 w 模块、两个 FIFO IP 和 PANGO RAM/GRS primitive 均直接编译实际文件。
所有生产/V5 源读取及父文件复制使用 `read_bytes()`；仅展示 diff 时按 GBK 解码。

候选完整保留动态地址、动态长度、参数和全部公共端口。仅 pixel_count 改为逐位
XOR/前缀进位加数据路径清零，保留 32 位宽度、reset/flush/SOF 优先级与原周期。
runner 审计公共声明、综合属性及去除计数器改动后剩余的全部 RTL token 一致。

全部结果独立存入 `../../receipts/cam6`。`results.json` 仅在三个实际 ModelSim
运行通过及受保护文件 SHA256 校验完成后生成。测试比较全部 20 个公共输出、566 位，
并核对 pixel_count/pixel_limit/diag_input_count；上位进位以双方配对状态 deposit 到达。
覆盖自然 FIFO 溢出、满时 reset 后完整帧恢复、短帧 restart、DMA abort、命令/数据背压、
cam enable、动态长度 0/1/7/129/半长度/端口最大值、地址边界和背压期间动态变化。

父绑定由 runner 在 `receipts/cam6/bindings` 生成独立字节副本，覆盖 V5 inputs/source
与 rtl 下全部原 ov5640_ddr 实例，清单见 `parent_bindings.json`。只替换实例模块类型，
保留父模块名、实例名、参数、端口、所有 GBK 注释及其他字节；反向替换必须恢复原文件。
其中活动 V5 cooperative top 的 cam6 和 ov5640_top 的原 DDR 都绑定候选；原 cam5 capture
wrapper 不变。历史 top/insert_sfp_block/HDMI 父文件也生成副本，避免漏掉原模块使用者。
这些副本是后续隔离集成的可审查输入，并未覆盖原父文件或登记至任何 PDS 工程。

保留原实现的 tag 地址语义：偏移由参数 `CAM_DATA_LEN << 4` 决定，而不是运行时
`cam_data_len`；运行时长度仍参与原 frame command、FIFO 与 pixel_limit 逻辑，未改成常量。

局限：实际仿真数据宽度 16、AXI 数据宽度 128、地址/命令长度宽度 32，长度参数跑
38400 和 2048；其他宽度的接口/非计数器逻辑一致由 token 审计证明，未额外仿真。
未做整机父层级 elaboration/仿真；未运行综合、PDS 或布线，因此没有 CECO
已消除、资源改变或 slack 改善的物理证据。V5 原 23/24 full_detail 保存在本回执目录。
已有 stream_capture runner、候选及回执，以及生产/V5/TC03/TC02 文件均受 SHA256 保护。
独立 DMA 子任务的可变 tests/receipts 不属于 cam6 输入，未纳入最终保护集合；cam6
脚本不写这些位置。首次回归三组仿真通过后，广义保护集合检测到 DMA 子任务并发更新；
该次变动保留在 `prior_run_concurrent_changes.json` 和 `prior_run_protected_sha256.json`，
随后以明确的本任务保护集合完整重跑。
