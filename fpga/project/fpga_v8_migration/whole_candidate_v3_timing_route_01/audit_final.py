"""Reuse exact v2 RAM/HSST physical audit with all outputs redirected locally."""
from build_candidate import *
from run_flow import local
from collections import Counter
def main():
    old=M/'whole_candidate_v2_route_01'
    summary=load('summarize_route',old/'summarize_route.py')
    summary.HERE=HERE;summary.EVIDENCE=HERE/'evidence_02';summary.EVIDENCE.mkdir(exist_ok=True)
    sys.modules['summarize_route']=summary
    runner=load('run_route',old/'run_route.py')
    runner.guards=lambda:json.loads((HERE/'protected_after.json').read_bytes());runner.inputs=local
    sys.modules['run_route']=runner
    source=(old/'audit_final.py').read_bytes()
    source=source.replace(b'fpga_v8_cooperative_top_v2.rtr',b'fpga_v8_cooperative_top_v2_rfg01.rtr')
    source=source.replace(b'max_path 15000',b'max_path 200000')
    source=source.replace(b'final_export_result.json',b'final_export_03_result.json').replace(b'final_export/',b'final_export_03/')
    scope={'__name__':'redirected_v2_final_audit','__file__':str(HERE/'audit_final.py')}
    exec(compile(source,str(old/'audit_final.py'),'exec'),scope)
    save('audit_reuse_provenance.json',{'source':str(old/'audit_final.py'),'sha256':sha(old/'audit_final.py'),'changes':['All write/output globals redirected to own candidate','New top report filename','Path limit raised to tool maximum 200000'],'old_files_modified':False})
    scope['main']()
    evidence=HERE/'evidence_02'
    final=json.loads((evidence/'final_sta_summary.json').read_bytes())
    assert final['negative_paths_match_summary_endpoint_total'],'Incomplete endpoint path export'
    final['timing_closed']=all(s['sum_failing_endpoints']==0 for s in final['all_corner_summaries'])
    final['scored_checks_closed']=final['timing_closed']
    final['implementation_signoff']=False
    final['guard_mapping_blocker']='guard_mapping_blocker.json'
    final['board_ready']=False
    save('evidence_02/final_sta_summary.json',final)
    paths=json.loads((evidence/'all_reported_failing_paths.json').read_bytes())
    save('evidence_02/failure_tally.json',{'total':len(paths),'by_path_type':dict(Counter(p['Path Type'] for p in paths)),
         'by_path_group':dict(Counter(p['Path Group'] for p in paths)),
         'guard_paths':[p for p in paths if any(k in (p.get('Endpoint') or '')+(p.get('Startpoint') or '') for k in ['rfg','fault','alive','link'])],
         'threshold_metadata_paths':[p for p in paths if any(k in (p.get('Endpoint') or '')+(p.get('Startpoint') or '') for k in ['threshold','select_q','changed_q'])]})
    stages={}
    for stage,name in [('compile','cmr.db'),('synthesize','snr.db'),('device_map','dmr.db'),('place_route','prr.db')]:
        db=HERE/stage/name
        if db.exists(): stages[stage]={'sha256':sha(db),'tables':summary.extract(db,stage)}
    save('evidence_02/stage_tables.json',stages)
    pins=stages.get('place_route',{}).get('tables',{}).get('pnr_io_report',{})
    base=json.loads((old/'evidence/route_summary.json').read_bytes())['stage_reports']['place_route']['tables']['pnr_io_report']
    assert pins['rows']==base['rows'],'PCB attributes changed'
    text=(HERE/'pnr_shell.log').read_text(errors='replace')
    compilelog=(HERE/'compile/run.log').read_bytes()
    elaborated=set(x.decode() for x in re.findall(rb'Elaborating module (\w+)',compilelog))
    structural=json.loads((HERE/'artifacts/structural_audit.json').read_bytes())
    required={n for n in structural['reachable_modules'] if n.endswith('_rfg01')}|{'fpga_v8_reset_fault_guard','block_motion_detector_tc01','ovreg_axil_decode_tc01','motion_stream_adapter'}
    assert required<=elaborated,('Missing actual elaborated modules',required-elaborated)
    assert not {'block_motion_detector','ovreg_axil_decode'}&elaborated,'Old correction modules actually elaborated'
    save('evidence_02/actual_elaboration.json',{'required':sorted(required),'elaborated':sorted(elaborated),'all_required_elaborated':True,'original_corrected_modules_elaborated':False,'compile_log_sha256':sha(HERE/'compile/run.log')})
    physical=[x for x in text.splitlines() if any(k in x.lower() for k in ['hold violation','hold timing','hold fix','hold violated','fix_hold','multi_corner','max_hold','route-2037'])]
    save('evidence_02/effective_physical_settings.json',{'lines':physical,'route2037': 'Route-2037' in text,'requested':json.loads((HERE/'physical_settings.json').read_bytes()),'pds_after_sha256':sha(HERE/'project_after_pnr.pds'),'impl_script':(HERE/'impl.tcl').read_text(errors='replace') if (HERE/'impl.tcl').exists() else None,'hold_fix_effectiveness_requires_log_review':True})
    save('evidence_02/pcb_pin_audit.json',{'gpio_count':len(pins['rows']),'all_rows_identical_to_completed_v2_route':True,'hsst_audit':'hsst_actual_phy_audit.json'})
    checks={stage:{k:v for k,v in data['tables'].items() if any(token in k for token in ['check_timing','clock','constraint','summary','resource'])} for stage,data in stages.items()}
    finaltables=json.loads((evidence/'final_sta_tables.json').read_bytes())
    checks['final_sta']={k:v for k,v in finaltables.items() if any(token in k for token in ['check_timing','clock','constraint','summary'])}
    save('evidence_02/clock_constraint_loop_latch_checks.json',checks)
    warnings=[x for x in text.splitlines() if x.startswith(('W:','C: STA-'))]
    save('evidence_02/warnings.json',{'all':warnings,'clock_constraints':[x for x in warnings if any(k in x.lower() for k in ['clock','constraint','match','short','latch','loop'])],'unscored_io':[x for x in warnings if 'delay' in x.lower() and any(k in x.lower() for k in ['input','output'])],'guard_async':[x for x in warnings if any(k in x.lower() for k in ['rfg','fault','alive','admission'])]})
    verify_protected();local()
    save('parent_handoff.json',{'status':'IMPLEMENTATION_SIGNOFF_BLOCKED_GUARD_MAPPING' if final['timing_closed'] else 'ROUTED_TIMING_NOT_CLOSED_AND_GUARD_MAPPING_BLOCKED',
        'timing_closed':False,'scored_checks_closed':final['timing_closed'],'implementation_signoff':False,'negative_paths':len(paths),'all_corner_summaries':final['all_corner_summaries'],
        'all_negative_paths':'evidence_02/all_reported_failing_paths.json','count_matches_summary':True,
        'physical_settings_review':'evidence_02/effective_physical_settings.json','ram_proof':'evidence_02/motion_routed_resource_proof.json',
        'unscored_io_paths':final['unscored_io_paths'],'board_ready':False,'hardware_accepted':False,
        'retained_limitations':['Unscored IO is not IO timing signoff','F2H/no host drain reset remains uncertified','Actual asynchronous reset/CDC paths require review; no added cuts'],
        'guard_mapping_blocker':'evidence_02/guard_mapping_blocker.json','next_required_fix':'Supported sequential mapping of guard asynchronous fault/sticky reconfiguration; eliminate N165 control-clock feedback without exceptions, then full-flow regression and routed STA',
        'protected_unchanged':True,'fdc_changed':False,'core_clock_mhz':131.25})
    print('Timing closed:',final['timing_closed'],'negative paths:',len(paths),flush=True)
if __name__=='__main__':main()
