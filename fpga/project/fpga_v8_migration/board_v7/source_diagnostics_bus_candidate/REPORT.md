# source diagnostics bus：隔离实现与本地证据

已在本目录实现 `v7_sdb.v`：精确高地址拦截、4相机源诊断实例、AXI-Lite适配、
16-byte寄存器协议、会话epoch、旧decoder透传。不是仅有建议。
**尚未顶层集成、未上板、未运行PDS/远程操作；没有改生产、冻结源码、IP或原诊断候选。**
Hindsight连接失败，本报告全部依据实际本地源码与仿真。

## 最关键的两项修订

1. **实际DMA确实会把4-byte紧密地址别名。** 冻结pcie_fifo第358/668行清除起始地址低4位，
   第363/671行按16-byte beat推进；axi_to_axi_lite本身透传地址，数据只取低32位。
   改为每相机0x100内五个16-byte间隔槽：STATUS、COMMAND、INDEX、DATA、EPOCH。
   每个槽单拍DMA访问，主机API必须检查16-byte对齐。适配器无法识别已被上游对齐掉的低位。
2. **撤销pending响应不合法。** 本实现不采纳原INTEGRATION第51行取消响应的建议。
   camera reset不触碰AXI事务状态：已承诺stalled R保留固定旧响应；已接受但源结果被reset
   清除的AR仍产生SLVERR。epoch和前后STATUS校验让主机识别多字段跨会话，避免拼新旧。

`INTEGRATION.md`给出完整接线、寄存器、主机读取顺序、reset合同、结构论证和物理门槛。

## 实跑结果

ModelSim SE-64 10.6e，2026-10-06 16:31:50–16:32:13：

| 回归 | 结果 | 原始证据 |
|---|---|---|
| 新总线集成TB | `SDB_ALL_PASS checks=11986` | simulation.log |
| 原候选逐拍源诊断TB，在新目录独立work重跑 | `SFD_DONE checks=2038 errors=0` / `SFD_ALL_PASS` | source_simulation.log |
| 两次编译 | 各0 errors / 0 warnings | compile.log / source_compile.log |
| 每次仿真 | 0 errors / 1 warning（-novopt） | 对应仿真日志 |
| 新模块名扫描 | `BYTE_MODULE_SCAN conflicts=0` | run.py标准输出 |
| 六个冻结依赖 | 固定SHA256匹配且测试前后不变 | run.py / source_hashes.txt |

onerror macro notice是ModelSim提示。没有把检查次数表述为形式证明覆盖率。

## 新总线TB覆盖

- 直接编译冻结128→32 bridge、冻结ovreg decoder、冻结capture和原源诊断模块；
  四个capture实际运行默认WAIT_FRAME=10，binding的negedge寄存器在TB中复现。
- 四相机ACQUIRE后遍历全部16字段；真实16 accepted bytes、8 aligned/native valid和格式值断言。
- AW先/W先/同时到达；握手后立即污染上游地址、数据，验证捕获；下游AW/W/AR周期性停顿。
- B与R背压保持；全程逐拍稳定性监视器；B stalled时并行读，camera reset不能清B。
- 重复ACQUIRE保持旧bank；新帧到来不覆盖；RELEASE后DATA报SLVERR。
- RVALID已经stalled时camera reset（2ns短脉冲，相对10ns host周期）仍返回原OKAY/原数据；
  epoch变化可见；其他相机lease不受影响。
- AR已握手、本地结果尚未返回时camera reset，最终返回SLVERR，不吞AR/不挂死。
- 多字段中途reset，无lease报错；恢复并重新ACQUIRE后读取成功但epoch不同，整包必须丢弃。
- 整个AXI接口reset可以清事务；复位后不续用旧lease。
- 四相机所有未定义读字节偏移遍历：+4/+8/+c、未对齐、空洞、COMMAND读均SLVERR；
  非法写偏移/INDEX越界/COMMAND双bit/部分WSTRB也报错。
- TB额外复现pcie_fifo的地址对齐表达式，证明+4归到+0；此部分是表达式模型，
  **没有**模拟整个pcie_fifo、PCIe IP或主机驱动。
- 冻结decoder的CAM1/2/3/4、PREP、motion和每相机CDC特殊读位置正确路由，旧写目标计数正确。
  区间外高地址和0x20001400原样透传，保留旧decoder语义；新区间不进入旧从机。

旧窗口从机在TB中是行为模型，不是完整生产CAM/PREP端点；本次证明的是新层的路由、
事务归属、地址/数据保持，不宣称验证整个旧端点系统。原源TB另覆盖640×480、奇数分段、
边界计数、overrun和独立复位等，详见source_simulation.log。

## 评审边界与复现

不支持冻结bridge未实现的burst/多beat拆分；使用单拍128-bit DMA，读取低32位。
新区间收到的未知地址不别名；区间外历史别名保持不变。epoch饱和fail-closed为结构审查项，
没有通过仿真穷举2^32次reset；短脉冲最小宽度、亚稳态、mailbox bundled-data约束需物理签核。
主机必须独占每相机lease并串行执行INDEX/DATA，整个AXI接口reset需丢弃旧上下文。

在工作区根目录：

```powershell
python project/fpga_v8_migration/board_v7/source_diagnostics_bus_candidate/run.py
```

脚本只写本目录的fixture.vh、work和证据日志；先校验固定依赖哈希和模块重名，
再运行两套回归，要求PASS且无FAIL，最后检查依赖未变化。
默认ModelSim路径 `C:/modeltech64_10.6e/win64`，可用MODELSIM_BIN覆盖。
address_evidence.txt为GBK源码字节级筛选后生成的地址与binding采样证据。

下一道集成门槛是review通过后另行修改顶层接线/导出旁接信号与CDC约束，
再做完整系统仿真、综合和物理签核。本候选没有完成这些门槛，不提供Fmax/资源/实板结论。
