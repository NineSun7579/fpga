build04 mapping60_01 实际结果

状态：FAIL_PRODUCTION60_MAPPING_ATTEMPT

仅这一新attempt；dev_map显式add_constraint原build04 clock与production60 LCF；remove_dups/const_prop/control_set_num均为官方选项0；无no_check，无时钟修改或新增timing exception。
741源字节/186登记独立复核：PASS
60精确综合绑定：PASS_EXACT_SYNTHESIS60_BINDING
控制器结果：FAIL
独立审计结果：FAIL

实际工具exit：0
拒绝日志行：[]
原生dmr错误：[]

实际失败（原样保留）：
```
Traceback (most recent call last):
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\mapping60_01\run_mapping60.py", line 191, in <module>
    try:main()
        ^^^^^^
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\mapping60_01\run_mapping60.py", line 167, in main
    cl=classify(g);types=sorted({r['type'] for r in cl['rows']})
       ^^^^^^^^^^^
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\runtime\analysis_tools\graph_adapter.py", line 200, in classify
    row=r.bind(cam,chain,bit);rows.append(row);lookup[(cam,chain,bit)]=row
        ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\runtime\analysis_tools\graph_adapter.py", line 105, in bind
    require(len(ds)==1,f'Unique actual Q driver required: {logical}: {ds}')
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\runtime\analysis_tools\graph_adapter.py", line 27, in require
    if not ok: raise RuntimeError(message)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Unique actual Q driver required: source_diagnostics/cameras[0].source/cr[0]: set()

```

后置审核：
```
Traceback (most recent call last):
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\mapping60_01\independent_review60.py", line 52, in <module>
    try:main()
        ^^^^^^
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\mapping60_01\independent_review60.py", line 20, in main
    result=load(E/'final_result.json');req(result['status']=='PASS_MAPPING_EXPORT_AUDIT60_ONLY','Attempt failed; production review BLOCKED')
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_04\evidence\runtime\mapping60_01\independent_review60.py", line 11, in req
    if not x:raise RuntimeError(m)
             ^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Attempt failed; production review BLOCKED

```

图/ADF/dmr/PCF/log及关键receipt SHA256见final_evidence_hashes.json。
原始源、build03、map02和保护IP前后审核见protection_before及protection_after或protection_after_failure。
未运行PNR/bit/远程/program；后续由主审决定全时序/IO/bit。
