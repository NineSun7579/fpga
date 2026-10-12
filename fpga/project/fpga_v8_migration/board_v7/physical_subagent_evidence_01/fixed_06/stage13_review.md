# 显式综合输入的 map 试验

stage_api12 的官方 runtime help 确认 dev_map 支持 -input_db_file 和 -force_to_run；define_current_design 只指定约束module，define_scope_collection定义查询表达式，save_adif说明是保存Current Editor，均不能据帮助推断能加载实际DB。

run_stage_map13.py 已在全局PDS/TA/de空闲后后台启动。独立stage_map13目录复制synthesis_epoch10真实综合DB，添加由其实际图生成的四路精确scalar约束，保留六份FDC的基础时钟及物理内容；调用dev_map -force_to_run -input_db_file。结果要求真实Device Map done、实际map DB、零E/Timing4003，且不能出现Compile/Synthesize阶段。源DB和1022保护清单启动前校验。该试验成功后仍需导出map对象并实际报告1280路径预算覆盖，不能只接受map done。

synthesis_epoch10/full_clock_leaf_review13.json通过另一套从顶层PCLK双向透明buffer/inverter展开的camera_leaves复核：四路完整叶节点数1068/1068/1075/1075，旧枚举遗漏0，补集仍748/748/755/755。

physical_exact_11在新综合覆盖复核阶段失败：camera0新增32个src_snapshot[64:95]/CLK实体不在其旧白名单，控制器未到PNR。该失败说明compile约束也会影响其它寄存器合并，不能把旧图中的固定集合继续当新图全集。
