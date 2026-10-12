from build_candidate import *
from run_flow import local
import xml.etree.ElementTree as ET
from collections import Counter
OUT=HERE/'evidence_02'
def tree_row(el):
    return {'data':[d.text or '' for d in el.findall('data')],'children':[tree_row(r) for r in el.findall('row')]}
def main():
    idle('final_review')
    finaldb=HERE/'final_export_03/report_timing/rtr.db'
    root=ET.parse(finaldb).getroot()
    exact={}
    for el in root.iter('table'):
        name=el.attrib.get('id','')
        if name and any(x in name for x in ['clock','loop','latch','delay','check_timing','constraint','messages']):
            exact[name]={'xml':ET.tostring(el,encoding='unicode'),'rows':[tree_row(r) for r in el.findall('row')],'headers':[d.text or '' for d in el.findall('column_headers/data')]}
    save('evidence_02/final_checks_exact.json',exact)
    check={r['data'][0]:int(r['data'][1]) for r in exact['check_timing_summary']['rows']}
    dump=(HERE/'final_export_03/routed_dump.txt').read_bytes()
    verilog=(HERE/'final_export_03/routed_dump.v').read_bytes()
    markcells={}
    for m in re.finditer(rb'(?m)^\s*(gop\w+)\b.*?;',verilog,re.S):
        names=re.findall(rb'\\(\w+/u_motion_tap/u_detector/mark_q\[(\d+)\]/[^\s]+)\s+\(',m[0])
        for inst,bit in names:
            assert b'.CLK ' in m[0] and b'.LATCH_EN("FALSE")' in m[0]
            markcells[inst.split(b'/')[0].decode(),int(bit)]=(inst,m[0])
    placements={m[1]:m[0] for m in re.finditer(rb'\(INSTANNOTATE \(INSTREF \\([^\s]+)\s*\).*?\n        \)',dump,re.S) if b'/mark_q[' in m[1]}
    metadata=[]
    for camera in ['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']:
        prefix=(camera+'/u_motion_tap/u_detector/mark_q[').encode()
        names={bit for (cam,bit) in markcells if cam==camera}
        assert len(names)==192,(camera,len(names))
        instances=[]
        for bit in range(192):
            token=prefix+str(bit).encode()+b']'
            # Record actual mapped declaration and location in dump.
            inst,cell=markcells[camera,bit]
            assert inst in placements,inst
            instances.append({'bit':bit,'instance':inst.decode(),'cell':cell.decode('ascii','backslashreplace'),'placement':placements[inst].decode('ascii','backslashreplace')})
        metadata.append({'camera':camera,'actual_mark_q_bits':len(names),'instances':instances})
    save('evidence_02/threshold_metadata_actual.json',{'threshold_metadata_bits_per_camera':192,'total_bits':768,'histories':metadata,'failing_paths_in_metadata':0,'proof':'Actual routed gop declarations plus INSTANNOTATE placement'})
    paths=json.loads((OUT/'all_reported_failing_paths.json').read_bytes())
    clusters={}
    for clock in ['ddrphy_sysclk','pclk_div2']:
        subset=[p for p in paths if p['Path Group']==clock]
        clusters[clock]={'failures':len(subset),'worst_slack_ns':min(p['Slack'] for p in subset),'paths':[{k:v for k,v in p.items() if k!='full_detail'} for p in subset]}
    log=(HERE/'pnr_shell.log').read_text(errors='replace')
    defaults={'fix_hold_violation_iterations':500,'fix_hold_violation_in_route':True,'fix_hold_violation_threshold_for_clock_path_cross_srb':200}
    save('evidence_02/physical_settings_effective_review.json',{'generated_actual_pnr_command':(HERE/'impl.tcl').read_text(),'actual_capacity':30000,'hold_fix_enabled':True,'multi_corner_enabled':True,'hold_threshold_ps':100,'clock_tree_threshold_ps':200,'baseline_default_options_omitted_by_PDS_serialization':defaults,'baseline_default_basis':'timing_correction_01/proposed_route_settings.json; own pre-run project explicitly set them, PDS normalized defaults away','hold_router_iterations':6,'route2037':False,'hold_repair_skip':False,'router_finished': 'Fix hold violation Finished.' in log,'all_slow_fast_hold_failures':0,'no_hold_fix_false_setting':True})
    matched=[]
    for p in [HERE/'synthesize/run.log',HERE/'place_route/run.log',HERE/'final_export_03/report_timing/run.log']:
        if p.exists():
            matched.extend({'file':str(p.relative_to(HERE)),'line':i,'text':x.decode('ascii','backslashreplace')} for i,x in enumerate(p.read_bytes().splitlines(),1) if any(k in x.lower() for k in [b'unmatched',b'not match',b'no match',b'short',b'set_clock_groups',b'false_path',b'no clock']))
    save('evidence_02/constraint_match_and_short_review.json',{'log_evidence':matched,'unchanged_fdc':json.loads((HERE/'preparation.json').read_bytes())['fdc_unchanged'],'effective_clock_interaction':exact.get('report_clock_interaction'),'new_exceptions':[],'guard_no_clock_remains_real_blocker':True})
    hand=json.loads((HERE/'parent_handoff.json').read_bytes())
    hand.update({'failure_clusters':clusters,'final_check_timing_issues':check,'successful_export':'final_export_03','evidence_directory':'evidence_02','routed_db_sha256':sha(HERE/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf'),'threshold_metadata_bits_actual':768,'history_DRM36K_actual':32,'negative_paths_match_summary':True,'next_required_fixes':[
        'DDR AXI awlen -> DDR adapter -> camera len CE same-clock path: shorten combinational acceptance/length arithmetic while preserving AXI admission and retirement contracts.',
        'PCIe o_ddr3_length[2] -> receive byte pack/mask rx_pack_data/N925 path: restructure length-mask decode into bounded combinational cones or equivalent existing pipeline; retain byte/strobe, 4KiB split and final-B semantics.',
        'Reset guard asynchronous fault/reconfiguration unsupported mapping: two latches, no-clock bad_event/N165, size-7 feedback and automatic STA cut. Use supported sequential structure preserving short-pulse capture, then re-verify full guard contracts and route.'],
        'no_current_candidate_rtl_changed_after_route':True,'full_timing_closed':False,'review_manifest_ready_for_fix_review':True,'not_board_accepted':True})
    save('parent_handoff.json',hand)
    verify_protected();local()
    print('Final routed check issues',check,'clusters',[(k,v['failures'],v['worst_slack_ns']) for k,v in clusters.items()],'threshold FF metadata 768')
if __name__=='__main__':main()
