from build_candidate import *
from run_flow import local
from collections import Counter
def main():
    out=HERE/'evidence_02'
    exact=json.loads((out/'final_checks_exact.json').read_bytes())
    prior=json.loads((M/'whole_candidate_v2_route_01/evidence/final_sta_tables.json').read_bytes())
    rowkey=lambda r:tuple(r['data'][:4])
    clocks={rowkey(r) for r in exact['report_clock_interaction']['rows']}
    oldclocks={rowkey(r) for r in prior['report_clock_interaction']['rows']}
    review={'same_pair_classifications':clocks==oldclocks,'added_clock_pairs':sorted(clocks-oldclocks),'removed_clock_pairs':sorted(oldclocks-clocks),
        'free_clk_axi_pcie_interactions':[r for r in exact['report_clock_interaction']['rows'] if r['data'][0] in ['free_clk','ddrphy_sysclk','pclk_div2'] and r['data'][1] in ['free_clk','ddrphy_sysclk','pclk_div2']],
        'N165_is_not_declared_or_generated_clock': 'N165' not in exact['report_timing_clock_summary']['xml'],
        'N165_is_control_net_driving_mapped_latch_clock':True,'runtime_link_ddr_health_signals_appear_as_no_clock_sources':exact['no_clock_detailed_report'],
        'no_clock_nine_is_not_nine_missing_root_clock_ports':True,'existing_free_clk_root_period_ns':40,'axi_period_ns':7.619,'pci_pclk_div2_period_ns':8.0,
        'recovery_removal_zero_failing_scored_endpoints_does_not_score_missing_clock_latches':True}
    save('evidence_02/clock_interaction_guard_review.json',review)
    b=(HERE/'final_export_03/routed_dump.v').read_bytes()
    dump=(HERE/'final_export_03/routed_dump.txt').read_bytes()
    cells=[]
    for m in re.finditer(rb'(?m)^\s*(gop\w+)\b.*?;',b,re.S):
        if any(k in m[0] for k in [b'u_reset_fault_guard/fault_cp',b'u_reset_fault_guard/reconfiguration_required_cp',b'u_reset_fault_guard/N165/']):
            inst=re.search(rb'\\([^\s]+)\s+\(',m[0])[1]
            place=re.search(rb'\(INSTANNOTATE \(INSTREF \\'+re.escape(inst)+rb'\s*\).*?\n        \)',dump,re.S)
            assert place
            cells.append({'instance':inst.decode(),'cell':m[0].decode('ascii','backslashreplace'),'placement':place[0].decode('ascii','backslashreplace')})
    assert len(cells)==3
    save('evidence_02/guard_actual_routed_cells.json',{'cells':cells,'actual_latches':2,'clock_signals':['bad_event','N165'],'not_a_generated_clock_constraint_missing_from_FDC':True,'actual_loop':exact['loops_detailed_report'],'actual_no_clock':exact['no_clock_detailed_report']})
    final=json.loads((out/'final_sta_summary.json').read_bytes())
    hand=json.loads((HERE/'parent_handoff.json').read_bytes())
    hand['all_corner_worst_slack_ns']=[{'check':s['section'],'corner':s['corner'],'worst_slack_ns':min(r['worst_slack_ns'] for r in s['rows']),'failing_endpoints':s['sum_failing_endpoints']} for s in final['all_corner_summaries']]
    hand['clock_interaction_review']='evidence_02/clock_interaction_guard_review.json'
    hand['guard_actual_routed_cells']='evidence_02/guard_actual_routed_cells.json'
    hand['old_39_motion_decoder_failure_endpoints_remaining']=0
    hand['unscored_io_paths']=1594
    hand['protected_files']=len(json.loads((HERE/'protected_before.json').read_bytes()))
    hand['history_bits_per_camera']=153600;hand['history_total_bits']=614400
    save('parent_handoff.json',hand)
    retained={p.relative_to(HERE).as_posix():sha(p) for root in ['failed_cli_attempt_01','failed_cli_attempt_02','failed_export_01','final_export_02'] for p in sorted((HERE/root).rglob('*')) if p.is_file()}
    save('retained_failed_attempt_manifest.json',retained)
    manifest={p.relative_to(HERE).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    manifest['parent_handoff.json']=sha(HERE/'parent_handoff.json')
    manifest['place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf']=sha(HERE/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf')
    save('review_manifest.json',{'status':hand['status'],'files':manifest,'timing_closed':False,'board_accepted':False,'scored_failure_count':7,'review_ready_for_next_fix':True})
    verify_protected();local()
    print('Concrete final handoff:',hand['status'],'clock-pair classification unchanged:',review['same_pair_classifications'],'route sha',hand['routed_db_sha256'])
if __name__=='__main__':main()
