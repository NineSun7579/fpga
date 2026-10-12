# Device Map 结构视图恢复

恢复12的真实结果：compile native export、综合、综合 native export成功；functional_map退出码1。functional_map.log记录60条ConstraintEditor-0062，缺少FloorPlan Structure View。后续SRAM任务因无BIT_MANIFEST.json退出，没有烧录新版本。

成功基线rebuild03/mapping02.log在应用布局前记录Building architecture floorplan logic view；该入口同时加载FDC和LCF。失败入口仅加载LCF，没有该视图初始化记录。

恢复13保持已成功的compile/synthesis ADF、741源文件和186登记、完整签名预算以及production60布局不变。在LCF之前加载只含get_ports {free_clk}查询的FDC，尝试触发官方结构视图初始化。该查询不新增或替换时序约束，是否有效以实际Device Map回执为准。

resume_map_view13.py保留失败回执并用新阶段名执行映射和导出；成功后接续原布局布线、双角时序和完整crossing覆盖核验及官方genbit。check_functional_bit09.py额外核对恢复脚本、查询、数据库和映射回执哈希。

目标验收仍需：新sbit及全部实际时序/IO保留证据；当次SRAM烧录和DONE回执；RK3568六路真实相机两帧截图及帧/tag进展；driving模式C5/C6、模型完成率、RAW和motion画面及错误日志审阅。单独构建成功、PCIe枚举或截图采集成功均不足以确认功能正常。
