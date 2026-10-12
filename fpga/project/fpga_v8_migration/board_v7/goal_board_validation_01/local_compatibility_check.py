"""Real RTR parser checks and tiny phase semantics; no fake delivery success."""
import copy
import ast
import json
from pathlib import Path
import py_compile
import re
import subprocess
import sys
import tempfile
import time
from new_program_candidate import HERE, BUILD, VENDOR, raw_summaries, records, audit_metadata, phase_pairs, phase_resets, sha, verify_owner_preflight
from new_prepare_delivery import assemble
from new_validate_board import verify_document as verify_board_document


def rejects(call):
    try:
        call()
    except (ValueError, FileNotFoundError, KeyError, TypeError):
        return True
    raise AssertionError('Expected fail-closed rejection')


def main():
    # Legacy synthetic boolean evidence must never satisfy final board scope.
    rejects(lambda: verify_board_document({'contract': 'boardValidation/v1', 'accepted': True,
                                           'reviewer': 'semantic-test-only', 'observations': {'display_normal': True}}))
    rejects(lambda: verify_board_document(json.loads((HERE / 'board_validation_v2.prepare.json').read_text())))
    board_tests = subprocess.run([sys.executable, str(HERE / 'test_board_validation_v2.py')],
                                 capture_output=True, text=True, check=False)
    assert board_tests.returncode == 0, board_tests.stderr
    for name in ('new_program_candidate.py', 'new_prepare_delivery.py', 'new_validate_board.py', 'local_negative_check.py'):
        py_compile.compile(str(HERE / name), doraise=True)
    vendor_tree = ast.parse(VENDOR.read_text(encoding='utf-8-sig'))
    run = next(n for n in vendor_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    assert [a.arg for a in run.args.args] == ['args', 'receipt', 'directory', 'bit', 'digest']
    # Evaluate only actual pure parse_log and its constants. Never import/run vendor.
    nodes = [n for n in vendor_tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('TARGET', 'ERROR') for t in n.targets)) or
             (isinstance(n, ast.FunctionDef) and n.name == 'parse_log')]
    scope = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(VENDOR), 'exec'), scope)
    old_run = HERE.parent / 'run_20261006_134504_c9abdebb'
    old_receipt = json.loads((old_run / 'receipt.json').read_text())
    old_log = old_run / 'log/cfg.log'
    stages, errors = scope['parse_log'](old_log.read_bytes().decode('gb18030'), 'sram')
    assert not errors and stages == old_receipt['stages'] and all(stages.values())
    migration = HERE.parents[1]
    v7 = migration / 'whole_candidate_v7_route_01/final_export/report_timing/fpga_v8_cooperative_top_v2_rfg01.rtr'
    exact = HERE.parent / 'physical_subagent_evidence_01/fixed_06/physical_exact_09'
    failed = exact / 'final_export/report_timing/v7_sdt_top.rtr'
    parsed = raw_summaries(v7)
    assert len(parsed['groups']) == 10 and parsed['unscored_io_paths'] == 1674
    rejects(lambda: raw_summaries(failed))
    target_checks = []
    for name in ('routed_mailbox', 'routed_reset'):
        path = exact / name / 'report_timing/v7_sdt_top.rtr'
        iterator = records(path)
        try:
            sample = next(iterator)
        finally:
            iterator.close()
        assert sample['start'].endswith('/CLK') and sample['end'].endswith('/RS')
        assert sample['corner'] == 'Slow' and sample['slack'] == 35.307
        target_checks.append({'path': str(path), 'bytes': path.stat().st_size,
                              'scope': 'first real record only; not full target acceptance', 'sample': sample})
    metadata = audit_metadata(exact / 'evidence/mailbox_routed_audit.json')
    assert metadata['passed'] is False and all(d['covered'] == 0 for d in metadata['details'].values())

    # Small semantic evidence only: synthetic phase names intentionally differ.
    # These objects are never written as a manifest, acceptance, or real build.
    mapping = {'resolved': [{'mapping': {'kind': 'register', 'launch_CLK': 'camera/mailbox[0]/CLK',
                                       'capture_D': 'camera/host[0]/D'}}]}
    graph = {'primitives': {'camera/mailbox[0]/opit_0': {'ports': {'CLK': {}, 'Q': {'direction': 'OUTPUT'}}},
                            'camera/host[0]/opit_1': {'ports': {'D': {'direction': 'INPUT'}}},
                            'camera/reset[0]/opit_0': {'ports': {'RS': {}}}},
             'pin_net': {'camera/mailbox[0]/opit_0/CLK': 'clock', 'camera/mailbox[0]/opit_0/Q': 'mail',
                          'camera/host[0]/opit_1/D': 'mail', 'camera/reset[0]/opit_0/RS': 'reset'},
             'netpins': {'mail': ['camera/mailbox[0]/opit_0/Q', 'camera/host[0]/opit_1/D']}}
    coverage = {'passed': True, 'errors': [], 'physical_pair_count': 1,
                'bindings': [{'logical': 'camera/mailbox[0]/CLK', 'physical': 'camera/mailbox[0]/opit_0/CLK'}],
                'pairs': [{'logical': ['camera/mailbox[0]/CLK', 'camera/host[0]/D'],
                           'physical': ['camera/mailbox[0]/opit_0/CLK', 'camera/host[0]/opit_1/D'], 'direct_Q_to_D': True}]}
    assert phase_pairs(mapping, coverage, graph) == {('camera/mailbox[0]/opit_0/CLK', 'camera/host[0]/opit_1/D')}
    bad = copy.deepcopy(coverage)
    bad['pairs'].append(copy.deepcopy(bad['pairs'][0]))
    rejects(lambda: phase_pairs(mapping, bad, graph))
    bad = copy.deepcopy(coverage)
    bad['pairs'][0]['logical'][1] = 'camera/wrong/D'
    rejects(lambda: phase_pairs(mapping, bad, graph))
    bad = copy.deepcopy(graph)
    bad['pin_net']['camera/host[0]/opit_1/D'] = 'unrelated'
    rejects(lambda: phase_pairs(mapping, coverage, bad))
    bad = copy.deepcopy(coverage)
    bad['bindings'].append({'logical': 'alias/CLK', 'physical': 'camera/mailbox[0]/opit_0/CLK'})
    rejects(lambda: phase_pairs(mapping, bad, graph))
    targets = {'ends': ['camera/reset[0]/P']}
    resets = {'bindings': [{'logical': 'camera/reset[0]/P', 'physical': 'camera/reset[0]/opit_0/RS'}]}
    assert phase_resets(targets, resets, graph) == {'camera/reset[0]/opit_0/RS'}
    rejects(lambda: phase_resets(targets, {'bindings': []}, graph))
    bad = copy.deepcopy(resets)
    bad['bindings'][0]['physical'] = 'camera/reset[0]/opit_0/P'
    rejects(lambda: phase_resets(targets, bad, graph))
    with tempfile.TemporaryDirectory(prefix='parser_semantics_', dir=HERE) as directory:
        diagnostic = Path(directory) / 'summary_label_only.rtr'
        diagnostic.write_bytes(v7.read_bytes().replace(b'Design Summary : All Constraints Met.',
                                                      b'Design Summary : Some Constraints Violated.'))
        assert raw_summaries(diagnostic)['unscored_io_paths'] == 1674
        # This is a semantic parser fixture, not an accepted real report.
    sources = json.loads((HERE / 'delivery_sources.prepare.json').read_text())
    rejects(lambda: assemble(sources))
    missing = copy.deepcopy(sources)
    missing.update(candidate_id='negative_schema_only', build_root=str(BUILD.resolve()))
    missing['artifacts'] = {k: str(HERE / ('missing_' + k)) for k in sources['artifacts']}
    rejects(lambda: assemble(missing))
    # Owner boundary semantics only; local text fixtures are not board evidence.
    with tempfile.TemporaryDirectory(prefix='owner_semantics_', dir=HERE) as directory:
        folder = Path(directory)
        files = {}
        for key in ('identity', 'boot_current', 'driver_current', 'ownership', 'cold_reset_action',
                    'boot_before', 'boot_after', 'pcie_reenumeration', 'driver_rebind'):
            path = folder / key
            path.write_text('current-boot' if key in ('boot_current', 'boot_after') else 'semantic-' + key)
            files[key] = {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}
        pre = {'contract': 'boardOwnerPreflight/v1', 'accepted': True, 'reviewer': 'semantic-test-only',
               'captured_unix': time.time(), 'delivery_manifest_sha256': 'semantic-manifest',
               'bit_sha256': 'semantic-bit', 'identity_matches_baseline': True, 'exclusive_owner': True,
               'driver_ready': True, 'boundary_kind': 'cold_reset_rebuilt', 'cold_reset_rebuilt': True,
               'dma_quiesced': False, 'artifacts': files}
        verify_owner_preflight(pre, 'semantic-manifest', 'semantic-bit')
        bad = copy.deepcopy(pre)
        del bad['artifacts']['cold_reset_action']
        rejects(lambda: verify_owner_preflight(bad, 'semantic-manifest', 'semantic-bit'))
        bad = copy.deepcopy(pre)
        bad.update(boundary_kind='proven_dma_idle', dma_quiesced=True)
        rejects(lambda: verify_owner_preflight(bad, 'semantic-manifest', 'semantic-bit'))
    proc = subprocess.run([sys.executable, str(HERE / 'new_prepare_delivery.py'), '--check'],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 1 and json.loads(proc.stdout)['status'] == 'blocked'
    report = {'board_validation_v2': 'PASS: negative semantic gates, real baseline chronology rejection; no actual acceptance',
              'legacy_v1_final_rejected': True, 'board_v2_prepare_rejected': True,
              'py_compile': 'PASS', 'vendor_contract': {'run_signature': 'args,receipt,directory,bit,digest',
              'programmer_sha256': sha(VENDOR), 'historical_cfg_log': str(old_log),
              'cfg_sha256': sha(old_log), 'stages_match_existing_receipt': True, 'vendor_run_called': False},
              'v7_raw_positive': {'path': str(v7), 'sha256': sha(v7),
              'groups': 10, 'unscored_io_paths': 1674, 'design_summary': parsed['design_summary']},
              'exact09_raw_negative': {'path': str(failed), 'sha256': sha(failed), 'rejected': True},
              'real_target_parser_samples': target_checks, 'exact09_mailbox_audit_false_preserved': True,
              'phase_semantics': 'PASS: translated suffixes, duplicate/wrong logical/bad net/non-injective rejection, routed reset conversion',
              'summary_label_only_semantic_fixture': 'PASS; no actual report modified',
              'assembler_incomplete_sources_rejected': True,
              'assembler_missing_artifacts_rejected': True,
              'owner_safety_boundary_semantics': 'PASS: documented rebuilt cold boot permitted with dma_quiesced=false; missing reset action/idle evidence rejected',
              'real_manifest_positive_test': False, 'remote_pds_program': False}
    (HERE / 'compatibility_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
