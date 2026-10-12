"""Only after real signoff: local bit generation and evidence-bound delivery adapter."""
from pathlib import Path
import json
import re
import subprocess
import sys
import time
from preflight import HERE, BOARD, load, sha, require, verify
from physical_flow import EVIDENCE, PDS, PROJECT, snapshot, protected, run, record, status

def bound(path):
    p = Path(path).resolve(strict=True)
    require(p.is_file() and p.stat().st_size > 0, 'Delivery artifact missing')
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}

def audit_sources():
    runtime=Path(__file__).resolve().parent
    return {'audit_fixed':str(runtime/'global_audit.py'),
            'verify_routed11':str(runtime/'routed_acceptance.py'),
            'summarize':str(runtime/'libraries/summarize_route.py'),
            'raw_audit':str(runtime/'libraries/raw_audit.py'),
            'consumer':str(BOARD/'goal_board_validation_01/new_program_candidate.py'),
            'routed_connection':str(BOARD/'goal_board_validation_01/routed_connection.py'),
            'targeted_reports':str(runtime/'targeted_reports.py'),
            'graph_adapter':str(runtime/'analysis_tools/graph_adapter.py'),
            'routed_truth_producer':str(runtime/'analysis_tools/routed_identity.py'),
            'routed_truth_reference':str(runtime/'libraries/routed_truth_reference.py.txt'),
            'endpoint_audit':str(runtime/'physical_flow.py'),
            'delivery_producer':str(Path(__file__).resolve()),
            'assembler':str(BOARD/'goal_board_validation_01/new_prepare_delivery.py')}

def target_log_sources():
    paths={};groups={}
    labels={'mailbox':['mailbox_batch_'+str(i).zfill(3) for i in range(21)],
            'reset':['routed_reset'],'reset_mpw':['routed_reset_mpw'],
            'sync_later':['routed_sync_later'],'mailbox_single_pair':['target_single_pair']}
    for group,queries in labels.items():
        groups[group]={'shell':[],'run':[]}
        for label in queries:
            for role,path in [('shell',EVIDENCE/(label+'.log')),('run',EVIDENCE/label/'report_timing/run.log')]:
                name=label+'_'+role+'_log';paths[name]=path;groups[group][role].append(name)
            paths[label+'_filter_guard']=EVIDENCE/(label+'_filter_guard.json')
    return paths,groups

def vendor_generated_sbit_check(path,expected_top='v7_sdt_top'):
    """Read the actual vendor container, not a suffix or renamed wrapper.

    This validates the generated Pango envelope; official gen_bit_stream and
    unchanged route/input provenance establish generation. No JTAG acceptance
    or vendor programming tool is invoked or inferred here.
    """
    p=Path(path).resolve(strict=True)
    with p.open('rb') as stream:header=stream.read(1024)
    magic=b'\x00\x09'+b'\x0f\xf0'*4+b'\x00PANGO MICROSYSTEMS, INC.\x00\x01'
    require(header.startswith(magic),'Not an actual Pango vendor bitstream container: '+str(p))
    pos=len(magic);fields={}
    for tag in b'abcdef':
        require(pos+3<=len(header) and header[pos]==tag,'Malformed vendor header tag')
        size=int.from_bytes(header[pos+1:pos+3],'big');pos+=3
        require(size>0 and pos+size<=len(header) and header[pos+size-1]==0,'Incomplete vendor header field')
        fields[chr(tag)]=header[pos:pos+size-1].decode('ascii');pos+=size
    require(fields['a']==expected_top and fields['b']=='Logos2-PG2L100H--6-FBG484' and
            fields['e']=='Fabric Compiler' and fields['f'].startswith('2022.2-SP6.4'),
            'Vendor bitstream top/device/compiler does not match this build')
    require(p.stat().st_size>1024,'Truncated vendor bitstream envelope without payload')
    return {**bound(p),'vendor_header':fields,'programming_acceptance_proven':False,
            'check_basis':'Actual Pango container/header plus fresh official gen_bit_stream provenance; no device operation'}

def select_bit(bits,started,route):
    candidates=[];rejected=[]
    for path in bits:
        require(path.resolve().is_relative_to((HERE/'generate_bitstream').resolve()) and path.stat().st_mtime>=started-2,
                'Bit output outside fresh isolated generation')
        try:candidates.append(vendor_generated_sbit_check(path))
        except (RuntimeError,UnicodeError) as exc:rejected.append({'path':str(path),'reason':str(exc)})
    record('bit_candidates.json',{'actual_vendor_outputs':candidates,'rejected_outputs':rejected,
           'route_sha256':sha(route),'selection_pending':True})
    choice=EVIDENCE/'bit_selection.json'
    if choice.exists():
        selection=load(choice)
        require(selection.get('contract')=='bitSelection/v1' and selection.get('reviewer') and
                selection.get('route_sha256')==sha(route),'Main bit selection must be explicit and route-bound')
        matches=[c for c in candidates if c['path']==selection.get('path') and c['sha256']==selection.get('sha256') and
                 c['bytes']==selection.get('bytes')]
        require(len(matches)==1,'Selected bit not an actual complete generated vendor output')
        selected=next(iter(matches));method='explicit main selection'
    else:
        sbits=[c for c in candidates if Path(c['path']).suffix.lower()=='.sbit']
        require(len(sbits)==1,'Require exactly one real generated .sbit; ambiguous/missing output needs explicit bit_selection.json')
        selected=next(iter(sbits));method='unique actual vendor .sbit; .bit wrappers not chosen by directory order'
    record('selected_bit_proof.json',{'selected':selected,'selection_method':method,'other_valid_outputs':candidates,
           'rejected_outputs':rejected,'route_sha256':sha(route),'official_generation_result':bound(EVIDENCE/'gen_bit_stream_result.json'),
           'official_generation_log':bound(EVIDENCE/'gen_bit_stream.log'),'remote_or_device_operation':False})
    return Path(selected['path'])

def delivery_sources(route):
    analysis = EVIDENCE / 'actual_post_constraints/analysis'
    bindings=load(EVIDENCE/'reset_bindings.json')['bindings'];targets=load(EVIDENCE/'reset_targets.json')
    ends={x['logical'] for x in bindings}
    require(len(ends)==len({x['physical'] for x in bindings})==32 and set(targets['ends'])==ends,
            'Delivery reset target/binding logical sets disagree; do not substitute synthesis pins')
    record('inputs_after.json', snapshot())
    guard = load(Path(__file__).resolve().parent/'baseline_data/protected_guard.json')
    record('protected_after.json', {p: sha(Path(p)) for p in guard})
    paths = {'route': route,
             'sta_raw': EVIDENCE / 'final_export/report_timing/v7_sdt_top.rtr',
             'sta_summary': EVIDENCE / 'evidence/final_sta_summary.json',
             'mailbox_raw': EVIDENCE / 'routed_mailbox/report_timing/v7_sdt_top.rtr',
             'mailbox_audit': EVIDENCE / 'evidence/mailbox_routed_audit.json',
             'reset_raw': EVIDENCE / 'routed_reset/report_timing/v7_sdt_top.rtr',
             'reset_audit': EVIDENCE / 'evidence/reset_routed_audit.json',
             'io_audit': EVIDENCE / 'evidence/io_audit.json',
             'hsst': EVIDENCE / 'evidence/hsst_actual_phy_audit.json',
             'motion': EVIDENCE / 'evidence/motion_routed_resource_proof.json',
             'routed_dump': EVIDENCE / 'final_export/routed_dump.txt',
             'routed_verilog': EVIDENCE / 'final_export/routed_dump.v',
             'coverage': EVIDENCE / 'coverageproof_routed.json',
             'routed_graph': EVIDENCE / 'routed/analysis/graph.json',
             'protected_before': EVIDENCE / 'protected_before.json',
             'protected_after': EVIDENCE / 'protected_after.json',
             'inputs_before': EVIDENCE / 'inputs_before.json',
             'inputs_after': EVIDENCE / 'inputs_after.json',
             'mapping': analysis / 'manifest.json',
             'reset_targets': EVIDENCE / 'reset_targets.json',
             'reset_bindings': EVIDENCE / 'reset_bindings.json',
             'reset_mpw_raw':EVIDENCE/'routed_reset_mpw/report_timing/v7_sdt_top.rtr',
             'reset_mpw_audit':EVIDENCE/'evidence/reset_mpw_routed_audit.json',
             'sync_later_raw':EVIDENCE/'routed_sync_later/report_timing/v7_sdt_top.rtr',
             'sync_later_audit':EVIDENCE/'evidence/sync_later_routed_audit.json',
             'single_pair_proof':EVIDENCE/'single_pair_filter_proof.json',
             'audit_execution_binding':EVIDENCE/'audit_parser_binding.json',
             'raw_audit_execution_binding':EVIDENCE/'raw_gate_reuse.json',
             'coverage_synthesis':EVIDENCE/'coverageproof_synthesis.json',
             'runtime_clockpair_proof':EVIDENCE/'runtime_clockpair_proof.json',
             'routed_endpoint_audit':EVIDENCE/'routed_endpoint_details.json',
             'selected_bit_proof':EVIDENCE/'selected_bit_proof.json',
             'bit_candidates':EVIDENCE/'bit_candidates.json',
             'generation_result':EVIDENCE/'gen_bit_stream_result.json',
             'generation_log':EVIDENCE/'gen_bit_stream.log'}
    logs,_=target_log_sources();paths.update(logs)
    return {k: bound(p) for k, p in paths.items()}

def finish_local_delivery(route):
    require(load(EVIDENCE / 'signoff.json')['passed'] is True, 'No full physical signoff')
    require(load(EVIDENCE / 'coverageproof_routed.json')['passed'] is True, 'No routed graph coverage')
    require(all(load(EVIDENCE / 'acceptance_gates.json').values()), 'Acceptance gates open')
    require(not (HERE/'generate_bitstream').exists(),'Refuse stale bit output folder/no-op')
    started=time.time()
    before = snapshot(); route_hash = sha(route)
    protected(); verify()
    marks = run('gen_bit_stream', [str(PDS), '-project', str(PROJECT), '-run', 'gen_bit_stream', '-work_dir', str(HERE)], HERE)
    require(any('done.' in m and ('Bit' in m or 'bit' in m) for m in marks), 'Official bit stage completion missing')
    require(snapshot() == before and sha(route) == route_hash, 'Bit generation changed inputs/route')
    bits = sorted(p for p in (HERE / 'generate_bitstream').rglob('*') if p.suffix.lower() in ('.bit', '.sbit') and p.stat().st_size > 0)
    require(bits and all(p.stat().st_mtime>=started-2 for p in bits), 'No fresh actual local bit output')
    selected=select_bit(bits,started,route)
    sources = delivery_sources(route)
    result = {'status': 'LOCAL_BIT_AND_SIGNOFF_PASS', 'build_root': str(HERE),
              'top': 'v7_sdt_top', 'manifest_sha256': sha(HERE / 'manifest.json'),
               'bits': [bound(p) for p in bits], 'selected_bit':bound(selected), 'artifacts': sources,
              'physical_signoff': True, 'remote_or_program': False,
              'delivery_contract': 'validatedDelivery/v1', 'delivery_adapter_pass': False}
    record('actual_result.json', result)
    record('delivery_inputs.json', result)
    status('LOCAL_BIT_SIGNOFF_PASS_ADAPTING_DELIVERY')
    script = BOARD / 'goal_board_validation_01/new_prepare_delivery.py'
    require(script.is_file(), 'Local bit/signoff complete; independent delivery adapter not available yet')
    acceptance = EVIDENCE / 'independent_acceptance.json'
    sta = load(EVIDENCE / 'evidence/final_sta_summary.json')
    limitations = {'unscored_io_paths': sta['unscored_io_paths'],
                   'unscored_io_note': 'Raw unscored IO records retained; PCB IO112 identity proven separately; unscored paths do not imply timed slack closure.',
                   'remote_or_program': False, 'board_verified': False}
    descriptor = {'contract': 'deliverySources/v1', 'candidate_id': 'source_diagnostics_timing_build_03',
                   'build_root': str(HERE), 'bit': str(selected), 'mailbox_expected_pairs': 1320,
                  'mapping_difference_reason': None,
                  'limitations': limitations,
                   'artifacts': {k: v['path'] for k, v in sources.items()},
                   'audit_sources':audit_sources(),'target_logs':target_log_sources()[1]}
    descriptor['artifacts']['acceptance'] = str(acceptance)
    record('delivery_sources.json', descriptor)
    vendor = BOARD.parents[1] / 'tools/program_100h_motion.py'
    request = {'contract': 'validatedDeliveryAcceptance/v1', 'accepted': False, 'reviewer': None,
               'candidate_id': descriptor['candidate_id'], 'build_root': str(HERE),
                'bit_path': str(selected), 'bit_sha256': sha(selected), 'bit_bytes': selected.stat().st_size,
               'programmer_sha256': sha(vendor), 'limitations': limitations,
               'artifact_sha256': {k: v['sha256'] for k, v in sources.items()},
                'audit_sha256': {k: sha(path) for k, path in descriptor['audit_sources'].items()},
               'note': 'Review request only. Main-session independent review must verify facts before supplying acceptance.'}
    record('independent_review_request.json', request)
    result['delivery_sources'] = bound(EVIDENCE / 'delivery_sources.json')
    result['status']='LOCAL_BIT_SIGNOFF_PASS_INDEPENDENT_ACCEPTANCE_REQUIRED'
    result['independent_acceptance_required']=str(acceptance)
    record('actual_result.json',result)
    status('LOCAL_BIT_PASS_WAIT_MAIN_INDEPENDENT_REVIEW_NO_DEVICE_OPERATION')
    return result
