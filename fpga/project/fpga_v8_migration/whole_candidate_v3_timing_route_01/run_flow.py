"""Fresh explicit full flow, no IP/bitgen, no random-seed retries."""
from build_candidate import *
from datetime import datetime,timezone
def local():
    pins=json.loads((HERE/'inputs_before.json').read_bytes())
    assert all(sha(HERE/p)==h for p,h in pins.items()),'Candidate input drift'
    return pins
def main():
    assert not (HERE/'pnr_started.json').exists(),'No overwrite/retry'
    assert not any((HERE/p).exists() for p in ['compile','synthesize','device_map','place_route'])
    pins=local(); verify_protected()
    helptext=(HERE/'pnr_help.log').read_bytes()
    flags={'-optimize_multi_corner_timing':None,'-fix_hold_violation':None,
           '-fix_hold_violation_iterations':500,'-fix_hold_violation_threshold':100,
           '-fix_hold_violation_in_route':'TRUE',
           '-fix_hold_violation_threshold_for_clock_path_cross_srb':200,
           '-fix_hold_violation_threshold_for_clk_tree':200,'-max_hold_violated_paths_num':30000}
    assert all((' '+k+' ').encode() in helptext for k in flags)
    pnr='pnr '+' '.join(k+(' '+str(v) if v is not None else '') for k,v in flags.items())
    script=HERE/'full_flow.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
                      'compile -top_module fpga_v8_cooperative_top_v2_rfg01\n'
                      'synthesize -ads -selected_syn_tool_opt 2\n'
                      'dev_map\n'+pnr+'\n',encoding='ascii')
    save('physical_settings.json',{'provenance':'pnr_help.log (installed PDS 2022.2-SP6.4 API)','command':pnr,'flags':flags,'timing_constraints_unchanged':True,'flow_recipe_reference':'whole_candidate_v2_route_01/impl.tcl','no_bitgen_no_ipgen':True,'launch_method':'-project project.pds -run pnr; physical options serialized in own project','full_flow_tcl_is_explicit_review_recipe':True,'actual_generated_recipe':'impl.tcl (PDS overwrites it per phase)'})
    idle('before_full_flow')
    command=[str(PDS),'-project',str(HERE/'project.pds'),'-run','pnr','-work_dir',str(HERE)]
    with (HERE/'pnr_shell.log').open('xb') as log:
        child=subprocess.Popen(command,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
        save('pnr_started.json',{'command':command,'pid':child.pid,'utc':datetime.now(timezone.utc).isoformat(),'full_flow':True})
        print('Full flow started PID',child.pid,flush=True)
        code=child.wait()
    verify_protected(); local()
    (HERE/'project_after_pnr.pds').write_bytes((HERE/'project.pds').read_bytes())
    text=(HERE/'pnr_shell.log').read_bytes()
    save('pnr_result.json',{'exit_code':code,'command':command,'finish_utc':datetime.now(timezone.utc).isoformat(),
         'completion_lines':[x.decode('ascii','backslashreplace') for x in text.splitlines() if b'Process "' in x and b'done' in x],
         'error_lines':[x.decode('ascii','backslashreplace') for x in text.splitlines() if x.startswith(b'E:')],
         'route2037':b'Route-2037' in text,'protected_unchanged':True,'local_sources_unchanged':True,
         'timing_signoff':False,'board_ready':False})
    print('Full flow finished exit',code,flush=True)
    sys.exit(code)
if __name__=='__main__':main()
