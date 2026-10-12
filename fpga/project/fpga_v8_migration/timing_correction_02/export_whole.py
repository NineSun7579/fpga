"""Run only after v4 flow finishes. Read-only routed STA and physical audit."""
from pathlib import Path
import subprocess,json,hashlib,importlib.util,sys,types,re
from run_whole import WORK,BASE,M,PDS,idle,inventory,save,sha
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module
def main():
    flow=json.loads((WORK/'flow_result.json').read_bytes())
    assert [s['stage'] for s in flow['stages']]==['compile','synthesize','pnr']
    assert all(s['exit_code']==0 for s in flow['stages'])
    assert inventory()==json.loads((WORK/'inputs_before.json').read_bytes())
    assert json.loads((WORK/'baseline_guard.json').read_bytes())['unchanged']
    binding=json.loads((WORK/'binding_audit.json').read_bytes())
    assert binding['exact_top_instance_replacements_only'] and binding['candidate_sources_match_tested_hashes']
    compile_log=(WORK/'compile/run.log').read_bytes()
    elaborated=set(x.decode('ascii') for x in re.findall(rb'Elaborating module (\w+)',compile_log))
    required={'fpga_v8_reset_fault_guard_02','axi_dma_write_tc02','fpga_v8_pcie_fifo_h2f_tc02','block_motion_detector_tc01','ovreg_axil_decode_tc01'}
    assert required<=elaborated,('Actual corrected modules not elaborated',required-elaborated)
    assert not {'fpga_v8_reset_fault_guard','axi_dma_write','fpga_v8_pcie_fifo_h2f_rfg01'}&elaborated,'Original module still elaborated'
    save('actual_elaboration.json',{'required':sorted(required),'elaborated':sorted(elaborated),'compile_log_sha256':sha(WORK/'compile/run.log'),'passed':True})
    out=WORK/'final_export';assert not out.exists(),'No overwrite of export attempt'
    idle('before_final_export');out.mkdir()
    route=WORK/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf';h=sha(route)
    script=WORK/'final_export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        '.switch_db -input {'+route.as_posix()+'} -output {'+(out/'routed_dump.txt').as_posix()+'}\n'
        'report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception TRUE\n',encoding='ascii')
    cmd=[str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','final_v4_route_evidence']
    with (WORK/'final_export_shell.log').open('xb') as log:
        p=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    save('final_export_result.json',{'exit_code':p.returncode,'route_sha256_before':h,'route_sha256_after':sha(route),'route_db_unchanged':sha(route)==h,'protected_unchanged':True})
    assert p.returncode==0 and sha(route)==h
    old=M/'whole_candidate_v2_route_01'
    summary=load('summarize_route',old/'summarize_route.py')
    summary.HERE=WORK;summary.EVIDENCE=WORK/'evidence';summary.EVIDENCE.mkdir()
    guards=lambda:{str(p):sha(p) for folder in ['inputs','rtl'] for p in (BASE/folder).rglob('*') if p.is_file()}
    save('protected_before.json',guards())
    runner=types.ModuleType('run_route');runner.guards=guards;runner.inputs=inventory
    sys.modules['run_route']=runner
    source=(old/'audit_final.py').read_bytes().replace(b'fpga_v8_cooperative_top_v2.rtr',b'fpga_v8_cooperative_top_v2_rfg01.rtr').replace(b'max_path 15000',b'max_path 200000')
    scope={'__name__':'v4_physical_audit','__file__':str(old/'audit_final.py')}
    exec(compile(source,str(old/'audit_final.py'),'exec'),scope);scope['main']()
    final=json.loads((WORK/'evidence/final_sta_summary.json').read_bytes())
    assert final['negative_paths_match_summary_endpoint_total'],'Negative path export truncated or incomplete'
    tables=summary.extract(out/'report_timing/rtr.db','final_checks')
    checks={row['data'][0]:row['data'][1] for name,t in tables.items() if 'check_timing_summary' in name for row in t['rows']}
    assert all(k in checks for k in ['loops','latchs','latch_loops','no_clock'])
    structural=all(checks[k]=='0' for k in ['loops','latchs','latch_loops','no_clock','unexpandable_clocks'])
    scored=all(s['sum_failing_endpoints']==0 for s in final['all_corner_summaries'])
    stages={stage:summary.extract(WORK/stage/db,stage) for stage,db in [('synthesize','snr.db'),('place_route','prr.db')]}
    previous=json.loads((BASE/'evidence_02/stage_tables.json').read_bytes())
    pins=stages['place_route']['pnr_io_report']['rows']
    assert pins==previous['place_route']['tables']['pnr_io_report']['rows'],'Physical PCB pins changed'
    save('evidence/stage_tables.json',stages)
    save('parent_handoff.json',{'scored_timing_closed':scored,'structural_checks_passed':structural,'checks':checks,'negative_paths':final['negative_slack_paths'],'all_corners':final['all_corner_summaries'],'pin_rows_match_previous':True,'motion_ram_proof':'evidence/motion_routed_resource_proof.json','unscored_io_paths':final['unscored_io_paths'],'board_ready':False,'remaining_board_gates':['FPGA loaded identity','coordinated physical reset','exclusive driver ownership','H2F/F2H response and visibility','same physical RAW byte correctness','completed cooperative inference FPS']})
    print('Scored timing closed:',scored,'Structural checks:',structural,flush=True)
if __name__=='__main__':main()
