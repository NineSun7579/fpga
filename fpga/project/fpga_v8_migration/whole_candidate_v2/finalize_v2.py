"""Finalize reviewable handoff; never run implementation or write outside v2."""
from pathlib import Path
import json
import hashlib
from build_candidate import HERE, OLD, TOP_NAME, TOP_HASH, write_json, protected_hashes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    review = load(HERE / 'artifacts/v2_review.json')
    evidence = load(HERE / 'artifacts/pds_evidence.json')
    structural = load(HERE / 'artifacts/structural_audit.json')
    assert review['status'] == 'compile_synthesis_verified_preliminary_unaccepted'
    assert all(s['pass'] and s['exit_code'] == 0 for s in evidence['stages'].values())
    assert review['mapped_check_timing'][0]['combinational_loops'] == 0
    protected = protected_hashes()
    before = load(HERE / 'artifacts/protected_hashes_before.json')
    assert protected == before, 'Protected file additions, deletions or byte changes detected'
    assert all(protected.get(p) == h for p, h in before.items())
    historical = load(OLD / 'artifacts/protected_hashes_before.json')
    assert all(protected.get(p) == h for p, h in historical.items()), 'Firstversion original production guard mismatch'
    write_json('artifacts/protected_hashes_final.json', {p: protected[p] for p in before})
    resources = evidence['synthesis_report']['resources']
    old_resources = load(HERE / 'baseline/pds_evidence.json')['synthesis_report']['resources']
    delta = {k: {'firstversion': old_resources[k]['used'], 'v2': v['used'],
                 'delta': v['used'] - old_resources[k]['used']} for k, v in resources.items()}
    handoff = {
        'title': '第二版完整隔离候选：父会话审查交接',
        'status': 'compile_synthesis_pass_preliminary_unaccepted_parent_review_required',
        'top_module': TOP_NAME, 'top_file': f'rtl/{TOP_NAME}.v', 'pds_file': 'project.pds',
        'baseline_top_sha256': TOP_HASH, 'candidate_top_sha256': sha(HERE / f'rtl/{TOP_NAME}.v'),
        'candidate_pds_sha256': sha(HERE / 'project.pds'),
        'immutable_firstversion_source_base': str(OLD),
        'snapshot_counts': {'frozen_inputs': 694, 'original_components': 12, 'additional': 5, 'active': 16},
        'source_changes_from_firstversion': 'Top unique rename plus exactly ARM controller and PCIe FIFO module-binding replacements; original instance names, parameters, connections unchanged',
        'production_rtl_semantic_fixes_during_pds': [],
        'actual_candidate_controller_elaborated': True,
        'old_controller_or_simulation_shell_elaborated': False,
        'full_apis_equal': True, 'named_port_width_checks': structural['new_interface_width_checks_passed'],
        'new_duplicate_modules': {}, 'new_implicit_or_multiple_driver_nets': [],
        'inherited_ip_duplicate_count': 11, 'constraints_unchanged': structural['constraints_unchanged'],
        'historical_pads': 112, 'hsst_bits': 14, 'six_cameras_and_motion_history_preserved': True,
        'core_wiring': 'core_clk=ddrphy_sysclk; axi_clk=core_clk; axi_rst=~ddr_init_done',
        'core_clock_mhz': 131.25, 'core_period_ns': 40 * 16 / 84,
        'capture_arm_operations': 499, 'capture_arm_events': 4288,
        'pcie_cases': 50, 'pcie_intentional_fault_cases': 4, 'f2h_parity_chunks': 305,
        'regression_receipts_and_source_hashes_verified': True,
        'final_check_timing': review['mapped_check_timing'], 'resource_delta_from_firstversion': delta,
        'ddr_core_timing': evidence['synthesis_report']['ddr_common_clock_slow_corner'],
        'timing_closed': False, 'inherited_ddr_hold_failures': 10,
        'protected_union_count': len(before), 'firstversion_historical_production_guard_count': len(historical),
        'current_production_source_ip_count': review['production_source_ip_count'],
        'current_protected_pds_count': review['protected_pds_count'],
        'requested_1191_count': 'Recount differs: 893 current source/IP files; 219 PDS paths in the complete protected union; historical firstversion guard is 1091. No count is fabricated.',
        'protected_before_after_final_exact': True,
        'pds_scope': 'Fresh attempt_01, sequential compile then synthesize; tasklist before every stage; no kills or cleanup; no PnR',
        'default_model_no_explicit_configuration': True,
        'blocked_for_acceptance': review['blockers'] + [
            'Endpoint eligible.addr_end_1 warning retained; parent mapped eligibility validation required',
            'Pre-route inherited hold violations and inherited incomplete external IO delay constraints remain'],
        'no_pnr_ssh_board_ip_generation_viewer_mutations': True,
        'evidence_files': ['artifacts/v2_review.json', 'artifacts/pds_evidence.json',
                           'artifacts/firstversion_to_v2.diff', 'artifacts/v2_byte_change_manifest.json',
                           'artifacts/pcie_production_byte_edits.json', 'artifacts/structural_audit.json',
                           'compile_01/attempt_01/evidence/check_timing_exact.json'],
    }
    write_json('artifacts/parent_handoff.json', handoff)
    write_json('artifacts/resource_delta.json', delta)
    write_json('artifacts/final_verification.json', {
        'status': 'PASS_WITH_RECORDED_ACCEPTANCE_BLOCKERS', 'scope': 'source + compile + synthesis only',
        'parent_handoff_sha256': sha(HERE / 'artifacts/parent_handoff.json'),
        'protected_external_files': len(before), 'external_mutations': [],
        'firstversion_historical_guard_verified': len(historical),
        'frozen_inputs': 694, 'original_components': 12, 'additional_components': 5,
        'compile_exit': 0, 'synthesis_exit': 0, 'loops': 0, 'latch_loops': 0, 'latches': 0,
        'no_pnr': True, 'no_hardware_acceptance_claim': True})
    excluded = HERE / 'artifacts/all_candidate_final_sha256.json'
    write_json('artifacts/all_candidate_final_sha256.json', {
        p.relative_to(HERE).as_posix(): sha(p) for p in sorted(HERE.rglob('*'))
        if p.is_file() and p != excluded})
    print(f'Finalized v2 handoff: {len(before)} protected files + historical {len(historical)} guard verified; compile/synthesis pass, loops/latches 0.')


if __name__ == '__main__':
    main()
