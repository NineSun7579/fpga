from build_candidate import *
a=load('static_v3_audit',V3/'prepare_candidate.py')
old=json.loads((V3/'artifacts/interface_width_audit.json').read_bytes())
new=json.loads((HERE/'artifacts/interface_width_audit.json').read_bytes())
key=lambda x:(x['instance'],x['port'],x['expression'],x['bits'])
assert {key(x) for x in old}<={key(x) for x in new}
adapter=(HERE/'rtl/motion_stream_adapter.v').read_bytes()
original=(V3/'inputs/source/motion/motion_stream_adapter.v').read_bytes()
schema=symbolic_schema(a,adapter)
assert schema==symbolic_schema(a,original)
assert len(schema)==6
top=json.loads((HERE/'artifacts/top_named_api_audit.json').read_bytes())
assert len(top)==31
instances=list(a.actual_instances(adapter))
detector=next(x for x in instances if x['module']=='block_motion_detector_tc01')
params=a.parameters((HERE/'rtl/block_motion_detector_tc01.v').read_bytes(),detector['parameters'],a.parameters(adapter))
assert params['SAMPLE_COLS']*params['SAMPLE_ROWS']==19200
assert set(detector['ports'])==set(symbolic_schema(a,(HERE/'rtl/block_motion_detector_tc01.v').read_bytes()))
save('artifacts/static_delta_audit.json',{'baseline_width_checks':len(old),'retained_original_width_checks':True,'current_width_checks':len(new),'added_width_checks':len(new)-len(old),'adapter_api_ports':len(schema),'top_named_api_instances':len(top),'adapter_original_api_identical':True,'corrected_detector_instantiation':detector,'resolved_detector_parameters':params,'history_depth':19200,'history_width':8,'history_bits_per_camera':153600,'four_history_total_bits':614400,'mapped_DRM36K_evidence_pending':True,'protected_before_files':len(json.loads((HERE/'protected_before.json').read_bytes()))})
verify_protected()
print('Baseline',len(old),'checks retained; total',len(new),'top API 31 / adapter API 6; histories 4 x 153600 bits')
