# 独立实际执行入口

新增 `run_controller.py`；未改主准备的 baseline/site 输入、check.py、README、OFFLINE_ONLY Tcl 或 prepared_hashes.json。无参数仅核验 prepared 哈希，不调用 PDS。

实际执行命令为 `python run_controller.py --run`。当前只准备，尚未执行。入口要求 map02 真实 final_result 与 independent_audit_result 均 FAIL，comparison_conclusion 已完成且全部 artifact hash 核验通过，然后等待前序实际控制器完整退出、全机 PDS/GUI idle，并取得 `Global\ov56401_PDS_single_instance` mutex。生产 map01/build02/source/旧 IP guard 在工具前后重核。

实际产物写入新建 execution/baseline 与 execution/site；拒绝重用已有 execution。prepared 工程/RTL/约束只复制，stages.tcl 的 OFFLINE_ONLY 原文不删不执行。实际 map Tcl 在 execution 下新建，使用官方 LCF PAP_LOC，三个整数选项为零，map 后真实 export_fdc，不加载 site_reference.pcf。每阶段单独日志、错误收据、ADF/native DB、raw dump、graph、真实端点及参数核验。错误、unknown/ignored/无效目标或 impl 均拒绝。

site 必须在实际生成 PCF 中逐一找到 actual mapped cell 对应 CLMA_33_450 / CLMA_45_462 与 impl_devCQ0，并在实际 export_fdc 找到相符的 PAP_LOC 目标绑定。缺失不是通过。raw PLACE 样本只作为测试输入依据，不代替这个证明。

结果为 actual_final_result.json；异常另存 actual_failure.json。PASS_METHOD_ONLY 只表示 twoFF 方法端点及约束有效，不表示生产 60 单元通过。若 baseline 已有两独立 FF，anti_packing_effect_demonstrated 必须 false。任何后续 map04 必须重新证明完整 28 sync + 32 reset 的 60 个不同 actual cells、D/CLK/reset/INIT/极性、功能周期及官方属性作用域。生产 gate 始终阻断，不运行 PNR、remote 或 device。
