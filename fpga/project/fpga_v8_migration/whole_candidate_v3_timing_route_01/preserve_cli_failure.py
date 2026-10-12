from build_candidate import *
idle('before_preserve_cli_failure')
assert not any((HERE/p).exists() for p in ['compile','synthesize','device_map','place_route'])
assert b"Only one of '-file' or '-project' can be specified." in (HERE/'pnr_shell.log').read_bytes()
out=HERE/'failed_cli_attempt_01'; out.mkdir()
for name in ['pnr_shell.log','pnr_started.json','pnr_result.json','full_flow.tcl','physical_settings.json','project_after_pnr.pds']:
    (HERE/name).rename(out/name)
save('failed_cli_attempt_01/reason.json',{'failure':'Mutually exclusive PDS CLI project/file switches; rejected before all compilation phases','correction':'Use verified -file/-work_dir/-project_name form to load project.pds in own work directory','physical_options_changed':False,'seed_changed':False,'sources_changed':False})
verify_protected()
