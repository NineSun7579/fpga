from build_candidate import *
idle('before_preserve_export_failure')
assert b'Value should be one between 1 and 200000' in (HERE/'final_export_shell.log').read_bytes()
out=HERE/'failed_export_01';out.mkdir()
for name in ['final_export','final_export.tcl','final_export_shell.log','final_export_result.json','final_export_started.json','export_command_provenance.json']:
    (HERE/name).rename(out/name)
save('failed_export_01/reason.json',{'reason':'Actual report_timing max_path upper bound is 200000','correction':'Use documented-by-validator maximum 200000 and verify every failure count matches exported paths','route_rerun':False,'routed_db_unchanged':True})
verify_protected()
