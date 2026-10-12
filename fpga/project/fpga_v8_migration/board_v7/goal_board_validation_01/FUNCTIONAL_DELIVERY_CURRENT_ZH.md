# 功能交付实际清单

本清单按用户最新“保证功能正常”范围执行，额外内部形式审计已停止。保留旧失败，仅把真实工程检查和板上功能作为推进依据。

| 交付项 | 实际证据/要求 | 当前核验 |
|---|---|---|
| 新候选构建 | 741源码与第四版一致、186登记；正确约束下综合/映射/PNR成功 | constraint_load_fix01 candidate02 compile及synthesis退出0；综合原生导出进行中，正确CDB尚未确认 |
| 时序与引脚 | DDR131.25MHz、mailbox15.238ns实际生效；真实setup/hold/recovery/removal/MPW；原生IO112位置/电气一致 | 旧replacement route负slack且继承旧CDB，无bit资格；新候选必须重新实测。旧replacement route IO112完整基线一致及HSST/motion保留已有记录 |
| 生成bit | 当次合格新route对应实际sbit，输入输出hash及成功日志 | 未完成；V7恢复镜像不能代替 |
| SRAM烧录 | 当次新sbit/hash、vendor成功、DONE=1，不写Flash | reboot_then_program_pcie_trial07已V7 DONE，但非新候选交付 |
| PCIe通信 | 真实host/root/0755:0755 endpoint/驱动/资源恢复，随后真实数据传输 | trial07自然及最终PCI列表空、无驱动节点；无root不能rescan。pcie_host_reprobe08实际重新probe主控推进中 |
| RK截图与功能 | 实际相机viewer身份，六路/RAW模型/motion运行，帧持续进展与错误日志，两组烧录后截图 | 未完成；MP4画面禁止用作相机运行证据 |

trial07原始result.json绑定boot_before=c1500212-6832-4215-a2b2-76b60c8c3858、boot_after=925a0f3d-b23b-46e5-b02b-b387a380402e及V7 SHA256 dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60。SRAM成功而PCI为空说明此顺序尚未恢复host，不能声称功能正常，也不归因硬件损坏。

下一步直接推进：新candidate正确CDB→实际映射/带hold修复PNR→必要验收→生成bit；板端在FPGA已DONE时一次标准platform host重新probe，恢复PCIe后才数据面与截图。两条工作互相独立，PDS/programmer依旧串行互斥。不再启动额外内部模型/alias/bank形式证明任务。

## 当前已核对的后续实证

- 新candidate02 mapping02_receipt.json退出0、errors为空；真实mapped数据库导出正在执行，不能仅凭命令成功宣告时序通过。continuation controller PID55876仍负责串行导出→实际PNR/holdfix→原生报告，不重复启动。
- pcie_host_reprobe08已实际执行一次3c0800000.pcie→rk-pcie/bind，rc0；完整Linux日志/枚举显示0755:0755 endpoint 0002:21:00.0，Gen2 x2与BAR资源。原端口此前unbound，故原先无root不能PCI rescan；此后host re-probe解决真实链路启动问题。
- 已验证同hash现存pango模块实际insmod成功，4个MSI已分配，设备节点存在且无owners；boot仍925a0f3d-b23b-46e5-b02b-b387a380402e。此为控制面恢复，不是DMA/相机功能PASS。
- 最终候选优先采用已有现场有效启动路径：真实reboot→新合格镜像SRAM/DONE→检查host/endpoint；若该实例确为unbound且无root，才对实际同实例执行一次标准host bind，再加载/验证现存driver。若host已bound或已有endpoint，按实际状态处理，不盲目重复bind、不使用GPIO144、不额外SBR。每次操作保留真实身份及回执，不继承V7编程hash或截图。
- driving-demo执行位目前0644属于持久admission，只有准备好当次实际功能测试后才对照原ledger/hash恢复原0755；不能直接将当前MP4进程当viewer。最终要明确相机模式启动，避免launcher残留--video参数。

## functional_route04实际推进

新的controller PID44500正在diagnostic02 PNR，工具PID70444/22896，主会话已检查真实日志处于placement、utilization49%，无最终STA。旧constraint_load_fix/rebuild03结果为1284实际pair（1280动态预算及4签名storage），不能冒称1280或据固定数量丢弃连接。

已读取controller.py和continue_functional.py：诊断之后串行fresh完整crossing约束compile/synth/map→functional PNR→global10/全部pair两角/签名单独报告。必要预算包含4签名，physical count来自新实际图；保持15.238ns/DDR131.25/原时钟关系。真时序负slack时尝试官方布局/路由优化的新独立attempt，旧失败保留。只有时序、实际budget覆盖和IO/HSST/motion保留全部通过后，才官方gen_bit_stream并产出BIT_MANIFEST.json。不手动签发旧countgate PASS。

主会话已准备capture_camera_session09.py，--help实际成功；未启动板上viewer或采集。入口只在实际camera driving-demo argv/exe匹配且无--video时取两组相隔10秒XWD/PNG/日志，前后绑定boot及proc starttime、当次bit和programreceipt。输出functional_pass=false，需实际帧进展与画面审阅才能最终判正常。采集入口存在不算已取得截图。

## 实际viewer模式覆盖修正

主会话字节读取已复现viewer源：CameraWorker在hdmiActive时暂停C1–C4；enableDrivingDemo实际setHdmiOverride(1)。因此driving-demo只采C5/C6，不能要求其日志证明六路，也不能当六路PASS。板级测试分两步：同一ELF先以--fullscreen --no-tracking --prefer-hdmifull off运行六路总览，无--camera/--video/--driving-demo，确认六路进展及画面；之后以目标--driving-demo配置实际运行模型/motion和C5/C6输入。capture_camera_session09支持--mode six-camera或driving并核对对应argv，两个阶段分别保留截图与日志，不修改模型或viewer语义。

## 诊断完成后的新阶段实证

诊断hold路径进一步核对：最差-1.336ns为C3同域cro/q[0]→mailbox[448]，数据段仅0.479ns，扣除CPR后clock skew=1.862ns；还包含C3 cq→mailbox、co计数器内部及ov5640_cdc/src_seq→src_snapshot（skew=2.509ns）。这些不是mailbox→host_bank跨域签名预算遗漏，补15.238ns约束不能解释或修复它们。若完整预算候选仍失败，应针对C3时钟分支路由/hold补偿修复，并复验原生双角结果；不得对这些同域路径使用falsepath或放宽预算。当前不修改正在执行的候选输入。

diagnostic02/RESULT.json已实际生成：15.238预算覆盖2560/2568，缺4签名连接的8条双角记录；最差Setup Slow -6.240/ Fast -3.296来自mailbox[480]→host_bank[480]的无预算签名路径。Hold Slow -1.336/Fast -0.740也是真失败，不能以签名预算修正代替实际hold复验；Recovery/Removal/MPW均非负。IO/HSST/motion保留检查通过，仅为诊断候选。

主会话实际进程检查显示控制器44500已进入functional_candidate01真实compile（PDS75040/80736），不是仍停在旧诊断布线。此fresh构建登记完整17word/512位约束，包含4签名预算；之后map/PNR需实测全部实际pair。functional_delivery_execute10/runner_corrected11.py（启动PID75892）等精确controller handle，只有合格新BIT_MANIFEST经过checker后才重启/新SRAM/hostbind/driver/两模式实测。两个实际控制器均有独立退出通知，不启动第二编程器。
