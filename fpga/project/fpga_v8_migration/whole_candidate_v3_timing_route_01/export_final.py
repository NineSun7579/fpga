"""Read-only slow/fast routed DB exports; all failing endpoint paths."""
from build_candidate import *
from run_flow import local
from datetime import datetime,timezone
def main():
    receipt=json.loads((HERE/'pnr_result.json').read_bytes())
    assert receipt['exit_code']==0,'Retain failed physical attempt; export requires routed DB'
    assert not (HERE/'final_export_02').exists(),'No export overwrite'
    local(); verify_protected(); idle('before_final_export')
    work=HERE/'final_export_02';work.mkdir()
    route=HERE/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf'; before=sha(route)
    script=HERE/'final_export_02.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        '.switch_db -input {'+route.as_posix()+'} -output {'+(work/'routed_dump.txt').as_posix()+'}\n'
        'report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception TRUE\n',encoding='ascii')
    command=[str(PDS),'-file',str(script),'-work_dir',str(work),'-project_name','final_route_evidence']
    save('export_command_provenance.json',{'sta_help':'whole_candidate_v2_route_01/timing_help.log','physical_export_reference':'whole_candidate_v2_route_01/final_export.tcl','path_limit':200000,'actual_tool_maximum':'failed_export_01/final_export_shell.log Flow-0188: range 1..200000','paths_per_endpoint':1,'filter':'slack < 0','all_summary_failure_counts_must_match_export':True,'no_num_paths_flag':'Installed report_timing help names -max_path and -nworst; -num_paths is absent','route_sha256_before':before})
    with (HERE/'final_export_02_shell.log').open('xb') as log:
        child=subprocess.Popen(command,cwd=work,stdout=log,stderr=subprocess.STDOUT)
        save('final_export_02_started.json',{'command':command,'pid':child.pid,'utc':datetime.now(timezone.utc).isoformat()})
        print('Final slow/fast all-negative-path export started',child.pid,flush=True)
        code=child.wait()
    local();verify_protected()
    save('final_export_02_result.json',{'exit_code':code,'command':command,'route_sha256_before':before,'route_sha256_after':sha(route),'route_db_unchanged':before==sha(route),'protected_unchanged':True,'local_sources_unchanged':True})
    assert sha(route)==before
    print('Read-only export completed',code,flush=True)
    sys.exit(code)
if __name__=='__main__':main()
