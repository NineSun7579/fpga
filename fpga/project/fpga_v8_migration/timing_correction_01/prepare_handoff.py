"""Read-only parent binding inspection; produce a reviewable integration manifest."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
V3=HERE.parent/'whole_candidate_v3'
V2=HERE.parent/'whole_candidate_v2_route_01'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
specs=[('rtl/fpga_v8_cooperative_top_v2_rfg01.v',b'ovreg_axil_decode ovreg_axil_decode_u',
        b'ovreg_axil_decode_tc01 ovreg_axil_decode_u'),
       ('inputs/source/motion/motion_stream_adapter.v',b'block_motion_detector #(',
        b'block_motion_detector_tc01 #(')]
bindings=[]
for name,old,new in specs:
    p=V3/name
    assert p.read_bytes().count(old)==1,(str(p),'binding occurrence mismatch')
    bindings.append({'parent_reference':str(p),'observed_sha256':sha(p),
                     'old_ascii':old.decode(),'new_ascii':new.decode(),
                     'expected_occurrences':1,
                     'instruction':'Apply to the parent-owned fresh candidate copy, not frozen v2. No port or parameter changes.'})
v2log=V2/'pnr_shell.log'
log=v2log.read_bytes().decode('ascii',errors='replace')
lines=[l for l in log.splitlines() if any(t in l for t in ('Route-2037','STA-3017','Timing-4105'))]
(HERE/'evidence/hold_route_abort.txt').write_text('\n'.join(lines)+'\n')
doc={'file':r'C:\pango\PDS_2022.2-SP6.4\doc\Pango_Design_Suite_User_Guide.pdf',
     'pdf_pages':[110,111,112,118,252,253]}
route={'vendor_document':doc,'existing_v2':{
    'Optimize Hold Timing In Route':True,
    'Max Number Of Hold Violated Paths To Fix':15000,
    'Optimize Multi-Corner Timing':False,'Optimize Hold Timing':False,
    'Fix Hold Violation Threshold(ps)':0,
    'Fix Hold Violation Threshold For Clock Path Cross SRB(ps)':200,
    'Fix Hold Violation Threshold For Clock Path On Clock Tree(ps)':100},
    'actual_abort':'Route-2037: 15016 paths exceeded 15000; hold violation fix stopped',
    'next_build_required_review':{
        'Max Number Of Hold Violated Paths To Fix':30000,
        'supported_setting_range':[0,100000],
        'setting_location':'Options > Place & Route > General',
        'cli_flag':None,
        'cli_note':'Installed manual documents the GUI name/range but does not list its CLI flag. Parent can inspect pnr -help in its authorized PDS session; no guessed flag supplied.'},
    'baseline_matched_physical_options_to_consider':[
        {'flag':'-optimize_multi_corner_timing','value':True},
        {'flag':'-fix_hold_violation','value':True},
        {'flag':'-fix_hold_violation_iterations','value':500},
        {'flag':'-fix_hold_violation_threshold','value':100},
        {'flag':'-fix_hold_violation_in_route','value':True},
        {'flag':'-fix_hold_violation_threshold_for_clock_path_cross_srb','value':200},
        {'flag':'-fix_hold_violation_threshold_for_clk_tree','value':200}],
    'limits':'Physical hold-route controls are not STA exceptions. They do not prove closure or necessarily fix asynchronous reset removal. PG2L100H uses single-thread router; manual PDF page 118 says its general/router options follow Logos. Verify actual accepted settings in the new PRR DB and final slow/fast STA.',
    'source_log':str(v2log),'source_log_sha256':sha(v2log),
    'executed':False}
(HERE/'proposed_route_settings.json').write_text(json.dumps(route,indent=2)+'\n')
manifest={'status':'RTL_FUNCTIONAL_REGRESSION_PASSED_ROUTED_TIMING_UNMEASURED',
    'owner_directory':str(HERE),'parent_v3_modified':False,
    'add_registered_sources':[{'file':str(p),'module':p.stem,'sha256':sha(p)} for p in sorted((HERE/'rtl').glob('*.v'))],
    'binding_replacements':bindings,
    'keep_original_definitions':'New module names are unique; originals may remain registered but are no longer instantiated on these two bindings.',
    'clock_mhz':131.25,'fdc_edits':[], 'new_false_paths':[], 'new_hold_cuts':[],
    'pipeline_contract':{'motion_sample_update_edges':2,'motion_result_after_end_edges':2,
                         'adapter_record_after_end_edges':3,'new_input_bubbles':0,
                         'new_transaction_edges':0,'history_bits_per_camera':153600,
                         'history_total_bits':614400,'new_threshold_metadata_bits_per_camera':192},
    'setup_target_counts':{'camera4_address_decode':25,'camera4_motion_reduce':14},
    'required_parent_evidence':['Fresh compile/map/route with integrated bindings and existing rfg01 protections.',
        'Verify effective PNR hold-repair path capacity and no Route-2037 skip.',
        'Final slow/fast all-clock STA including setup, hold, recovery, removal and min pulse.',
        'Confirm four 19200x8 read-first histories remain inferred RAM; FF cost is RTL metadata, not measured mapping.',
        'Inspect new local threshold-forwarding register paths as well as former global-reduction endpoints.',
        'Review missing IO delays separately; do not count unscored IO as timing closure.'],
    'regression_result':json.loads((HERE/'regression_result.json').read_text()),
    'four_regression_result':json.loads((HERE/'four_regression_result.json').read_text()) if (HERE/'four_regression_result.json').exists() else {'status':'RUNNING'},
    'protected_protections':['No PCIe/H2F/ARM RTL changes; byte packing/strobe, 4KiB split, final B retirement remain parent sources.',
        'No reset-fault-guard RTL changes; rfg01 startup/datafault drain remain parent sources.',
        'No changes to camera raw DDR/NPU data path, event FIFO, history storage template or motion ABI.'],
    'no_pds':True,'no_ssh':True}
(HERE/'parent_handoff.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'bindings':bindings,'four':manifest['four_regression_result']['status'],
                  'required_hold_repair_capacity':30000},indent=2))
