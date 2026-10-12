# TC05 / V7 全流程验收（构建进行中，物理验收未完成）

- [x] 主助手确认 `receipts/detector_20261006_121243_378185/results.json` 真实完成，运行 `python -B accept_regressions.py` 返回 passed=true，结果 SHA256 为 `1da1431ad4d535542c903c7eec821279d129b0474e37bb11d8b9d0b757bb92e0`。
- [x] 独立核验候选/runner/全部编译输入、17份artifact及563个保护文件哈希；门槛检查5组paired/8组stress、三组adapter集成及four-stream日志通过。测试结果不代表物理时序已闭合。
- [x] `accept_regressions.py` 已核验TC04六模块原RTL及全部回归哈希；V7仅新增detector修正，父adapter另存副本。构建后仍需再次核验。
- [x] `python -B check_reuse.py`：9个脚本语法、精确双层复用、冻结V6父绑定规划均通过。
- [ ] **仅主助手启动构建**：`python project/fpga_v8_migration/timing_correction_05/run_whole.py`。V7目录必须不存在，禁止覆盖历史尝试。从V6 inputs/rtl/project冻结副本构建，全流程逐阶段PDS单实例门槛。
- [ ] 保留V6唯一 -0.037ns WEA[0]失败证据及其路由、工程、全部源码/evidence哈希，构建后再次核验。绝不修改V6原件。
- [ ] 完整审核全部非生成文件登记/格式/顺序、器件/全部option、全部注册父文件实例替换；实际compile必须展开TC05与TC04六模块、TC03 adapter、TC02 FIFO、reset guard，禁止旧detector展开。允许保留未登记TC03旧文件，但TC05必须绑定真实回归候选哈希。
- [ ] `python project/fpga_v8_migration/timing_correction_05/finish_when_ready.py <V7 run_whole Python PID>`：主助手可挂接现有构建完成事件，依次export/generate/verify；任一失败停止。也可主助手串行运行这三个脚本。
- [ ] 最终Slow/Fast × Setup/Hold/Recovery/Removal/Minimum Pulse Width十组STA均非空、每行endpoint>0、slack≥0、TNS=0、零违例；独立重读原始报告，负路径导出完整且为空，结构门槛全部0。
- [ ] 原始物理pin rows与V6逐行相等且非空，HSST sites/dedicated connections保持；实际路由history证明32 DRM / 614400 bits。
- [ ] 继承TC04回执和TC03 adapter/历史motion回执全部哈希核验；TC03旧detector回执核验只证明历史基线，V7实际detector由TC05结果核验。TC02 transport/FIFO/guarded FIFO/reset原件比较与哈希门槛保留。
- [ ] 本地bitstream生成只在上述门槛通过后；manifest含V7标识、项目/源码/路由/bitstream/evidence哈希、TC05真实results和全部artifact逐字节副本。独立verify再次比较原件回执、全部hash及完整STA。
- [ ] 不烧录；`programming_performed=false`、`board_verified=false`，保留未评分IO路径与板级剩余门槛，不声称板级验证完成。

主助手已启动 `python -u run_whole.py`（PID 40656），并启动 `python -u finish_when_ready.py 40656` 挂接完成事件。启动动作不代表构建完成；未勾选项仍需实际最终证据。
