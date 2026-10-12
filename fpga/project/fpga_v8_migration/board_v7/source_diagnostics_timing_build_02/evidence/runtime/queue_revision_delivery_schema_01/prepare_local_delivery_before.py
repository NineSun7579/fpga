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

def delivery_sources(route):
    analysis = EVIDENCE / 'actual_post_constraints/analysis'
    g = load(analysis / 'graph.json'); c = load(analysis / 'classification.json')
    ends = sorted({x['reset'] for x in c['reset']})
    require(len(ends) == 32, 'Delivery reset32 targets missing')
    record('reset_targets.json', {'ends': ends, 'source_graph_sha256': sha(analysis / 'graph.json')})
    record('inputs_after.json', snapshot())
    guard = load(BOARD / 'source_diagnostics_route_01/build01_guard.json')
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
             'reset_bindings': EVIDENCE / 'reset_bindings.json'}
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
    sources = delivery_sources(route)
    result = {'status': 'LOCAL_BIT_AND_SIGNOFF_PASS', 'build_root': str(HERE),
              'top': 'v7_sdt_top', 'manifest_sha256': sha(HERE / 'manifest.json'),
              'bits': [bound(p) for p in bits], 'artifacts': sources,
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
    descriptor = {'contract': 'deliverySources/v1', 'candidate_id': 'source_diagnostics_timing_build_02',
                  'build_root': str(HERE), 'bit': str(bits[0]), 'mailbox_expected_pairs': 1320,
                  'mapping_difference_reason': None,
                  'limitations': limitations,
                  'artifacts': {k: v['path'] for k, v in sources.items()}}
    descriptor['artifacts']['acceptance'] = str(acceptance)
    record('delivery_sources.json', descriptor)
    sys.path.insert(0, str(script.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location('isolated_delivery_assembler', script)
    assembler = importlib.util.module_from_spec(spec); spec.loader.exec_module(assembler)
    vendor = BOARD.parents[1] / 'tools/program_100h_motion.py'
    request = {'contract': 'validatedDeliveryAcceptance/v1', 'accepted': False, 'reviewer': None,
               'candidate_id': descriptor['candidate_id'], 'build_root': str(HERE),
               'bit_path': str(bits[0].resolve()), 'bit_sha256': sha(bits[0]), 'bit_bytes': bits[0].stat().st_size,
               'programmer_sha256': sha(vendor), 'limitations': limitations,
               'artifact_sha256': {k: v['sha256'] for k, v in sources.items()},
               'audit_sha256': {k: sha(p) for k, p in assembler.AUDITS.items()},
               'note': 'Review request only. Main-session independent review must verify facts before supplying acceptance.'}
    record('independent_review_request.json', request)
    result['delivery_sources'] = bound(EVIDENCE / 'delivery_sources.json')
    if not acceptance.is_file():
        result['status'] = 'LOCAL_BIT_SIGNOFF_PASS_INDEPENDENT_ACCEPTANCE_REQUIRED'
        result['independent_acceptance_required'] = str(acceptance)
        record('actual_result.json', result)
        status('LOCAL_BIT_PASS_WAIT_MAIN_INDEPENDENT_REVIEW_NO_DEVICE_OPERATION')
        return result
    # The independent assembler explicitly forbids manufacturing accepted/reviewer.
    require(acceptance.is_file(), 'Actual local bit/signoff complete; main-session independent acceptance needed for validatedDelivery/v1')
    command = [sys.executable, str(script), '--sources', str(EVIDENCE / 'delivery_sources.json'), '--check']
    record('delivery_adapter_launch.json', {'command': command, 'script_sha256': sha(script)})
    completed = subprocess.run(command, cwd=HERE, capture_output=True)
    (EVIDENCE / 'delivery_adapter.log').write_bytes(completed.stdout + completed.stderr)
    require(completed.returncode == 0, 'Delivery schema adaptation failed; bit/result preserved')
    document = assembler.assemble(descriptor)
    manifest = HERE / 'delivery_manifest.json'
    require(not manifest.exists(), 'Delivery manifest already exists; preserve prior review')
    manifest.write_bytes((json.dumps(document, indent=2, ensure_ascii=True) + '\n').encode('ascii'))
    consumer = BOARD / 'goal_board_validation_01/new_program_candidate.py'
    # Only the read-only verifier function: no main, no remote/program execution.
    spec = importlib.util.spec_from_file_location('local_delivery_check', consumer)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.verify(manifest)
    result['delivery_adapter_pass'] = True
    result['delivery_manifest'] = bound(manifest)
    record('actual_result.json', result)
