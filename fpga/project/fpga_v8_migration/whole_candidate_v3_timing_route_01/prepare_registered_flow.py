from build_candidate import *
idle('before_restore_registered_project')
assert b'Flow-0001: There are no design files' in (HERE/'pnr_shell.log').read_bytes()
assert not any((HERE/p).exists() for p in ['synthesize','device_map','place_route'])
out=HERE/'failed_cli_attempt_02';out.mkdir()
for name in ['pnr_shell.log','pnr_started.json','pnr_result.json','full_flow.tcl','physical_settings.json','project_after_pnr.pds']:
    (HERE/name).rename(out/name)
if (HERE/'compile').exists(): (HERE/'compile').rename(out/'compile')
generated=(HERE/'project.pds').read_bytes()
(out/'pds_serialized_options.pds').write_bytes(generated)
options=re.search(rb'\(_command cmd_pnr(.*?)\n\s*\)',generated,re.S)[1]
# Extract exact PDS-authored option records (switch/integer types proved by PDS).
records=re.findall(rb'\(_option [^\r\n]+',options)
assert any(b'max_hold_violated_paths_num (_integer 30000)' in x for x in records)
records += [b'(_option fix_hold_violation_iterations (_integer 500))',
            b'(_option fix_hold_violation_in_route (_switch ON))',
            b'(_option fix_hold_violation_threshold_for_clock_path_cross_srb (_integer 200))']
project=(HERE/'project_before_options.pds').read_bytes()
anchor=b'(_command cmd_pnr'
assert project.count(anchor)==1
project=project.replace(anchor,anchor+b'\n'+b'\n'.join(b'            '+x for x in records))
(HERE/'project.pds').write_bytes(project)
(HERE/'project_before_pnr.pds').write_bytes(project)
save('serialized_option_provenance.json',{'pds_authored_records':[x.decode() for x in records],'source':'failed_cli_attempt_02/pds_serialized_options.pds','capacity_option_confirmed_by_help':True,'default_options_accepted_in_previous_script':{'fix_hold_violation_iterations':500,'fix_hold_violation_in_route':True,'fix_hold_violation_threshold_for_clock_path_cross_srb':200},'correction':'-file creates a source-empty project; preserve failure then restore registered candidate and use -project -run pnr','no_physical_attempt_completed':True})
verify_protected()
