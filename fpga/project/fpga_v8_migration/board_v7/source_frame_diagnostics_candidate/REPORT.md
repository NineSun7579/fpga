# board_v7 帧源诊断候选：本地 RTL 验证

仅在本目录新增候选 RTL、TB、脚本与报告。没有改生产/冻结/IP/远程/PDS，没有接入或上板。
Hindsight 工具连接失败，本次依据本地源码及现有诊断报告工作。

## 结果

ModelSim SE-64 10.6e，2026-10-06 16:11:55–16:12:17：
`SFD_DONE checks=2038 errors=0`，`SFD_ALL_PASS`。
编译 0 errors / 0 warnings；仿真 0 errors / 1 warning（环境继承 -novopt）。
重跑 vlib 的 library-already-exists 提示不影响回归；onerror macro notice 为工具提示。
冻结 capture 与 binding 前后 SHA256 一致，记录于 source_hashes.txt。

| 验证 | 结果 |
|---|---|
| 正常 640×480，480×1280 bytes | bytes=614400；segments=480；odd=0；两种valid均307200 |
| 全尺寸，1/2/7 行拆为639+641，间隔一拍HREF低 | bytes仍614400；segments=481/482/487；odd=2/4/14；valid=307199/307198/307193 |
| 7+9 byte，间隔单拍低 | bytes=16；segments=2；odd=2；valid=7 |
| 少两个byte，1278-byte片段 | valid=639，odd=0 |
| 7-byte片段紧邻VSYNC | odd=1；valid=3；gap=0，边界结束片段未漏计 |
| 空帧 | byte/valid/segment=0，gap不可用标记正确 |
| 70000拍尾空白 | gap=65535，饱和可见 |
| 保持lease期间再来5帧 | 全16字段不变；overrun=1；释放后seq=7，prev是紧邻第6帧而非旧lease |
| 原始HREF跨VSYNC片段 | clipped可见；相邻aligned=4/5、native=5/4，总数9守恒；同时记录VSYNC重叠byte/valid |
| 额外注入边界valid | 边界native标志、VSYNC高期间valid总数可见；不是字节payload注入 |
| host单独复位、cam单独复位、错开放复位 | 会话清除，无旧快照重放；新快照需重新ACQUIRE；未获取数据读取报错 |
| 8位同构prefix counter | 1200拍increment/hold、多次wrap及clear-seed检查通过 |

**这些数值模型不证明实板 HREF 出现单拍低或奇数片段。** 它们证明新诊断能区分
“字节总量少”“字节总量相同但奇数分段多”“capture 边界窗口位移”。
source307199/198/193 的实板原因仍未确定，不能改称硬件问题。

TB 直接编译冻结 cmos_capture（DATA_WIDTH=16，DELAY=2，默认WAIT_FRAME=10），
并复现 binding 中不带复位的 negedge 输出寄存器；没有 force DUT 计数器或改冻结文件。
独立逐拍 scoreboard 对 byte、segment、odd、aligned/native 计数做比对。
最初边界断言用“片段在marker开始”的刺激，未产生预期窗口位移；修正为
“首字节在marker之前、第二字节恰在marker”的真正跨界刺激，保留clipped标志并通过相邻守恒检查。

## 实现要点与资源边界

v7_sfd_candidate.v 内含两个唯一模块名 v7_sfd_candidate / v7_sfd_counter。
byte/valid主计数用24位，segment/odd/gap用16位，seq用32位；所有加一计数均用4位slice+
注册prefix，晚到的事件使能不经过32位串行进位。gap饱和；其他计数溢出使帧bad。
源bank与主机bank各512位逻辑声明，常量及零扩展位可综合消除；没有图像RAM、DSP、payload FIFO。
按寄存器声明粗算总存储低于1.6K bit/相机，常量裁剪后更少。这是结构规模，不是PDS资源报告；
未运行综合/布局布线，不宣称达到任何Fmax或CDC物理签核。

跨域为稳定mailbox+request/ack握手，主机显式ACQUIRE/RELEASE保证全部字段同一快照。
busy时丢弃新快照并置sticky overrun，不写半包、不阻塞RAW。
prev统计每帧更新，不受主机丢快照影响。读无lease或非法word返回read_error，
复位后不会自动租用新帧补到旧读取中。详细epoch、字段、CDC约束、主机流程见 INTEGRATION.md。

## 复现命令

在工作区根目录运行：

```powershell
python project/fpga_v8_migration/board_v7/source_frame_diagnostics_candidate/run.py
python project/fpga_v8_migration/board_v7/source_frame_diagnostics_candidate/audit.py
```

run.py 对 GBK 源使用 bytes 正则扫描模块重名；本次扫描420个源（并行工作增加文件会改变数量），
冲突0；随后调用 vlib/vlog/vsim，断言最终PASS及无FAIL，校验冻结输入哈希。
输出 compile.log、simulation.log、source_hashes.txt 与本地work库。
audit.py 生成 address_audit.txt：建议新精确地址0x20001000..0x200013ff，
避开已占用CAM/PREP/motion与整个COOP/CAPL endpoint窗口；**现有低位decoder会产生别名，
必须新增上游精确拦截，当前地址不可直接使用**。没有实现AXI适配器或修改top/PDS。

地址审计实跑输出：`ADDRESS_AUDIT files=7 candidate_literal_conflicts=0`。
另在候选目录执行 `C:/modeltech64_10.6e/win64/vlog.exe v7_sfd_candidate.v`，
2026-10-06 16:16:03 纯Verilog（不加-sv）编译同样0 errors / 0 warnings。
