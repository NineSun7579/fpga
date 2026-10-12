"""Final file/process audit only; all output stays inside the candidate."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from build_candidate import HERE, COMPONENTS, TOP_NAME, TOP_HASH, protected_hashes, write_json, save


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    report = json.loads((HERE / 'artifacts/pds_evidence.json').read_bytes())
    run = HERE / report['run_directory']
    assert run.resolve().is_relative_to(HERE)
    assert all(stage['pass'] and stage['exit_code'] == 0 for stage in report['stages'].values())
    assert report['candidate_top_sha256'] == sha(HERE / f'rtl/{TOP_NAME}.v')
    assert report['candidate_pds_sha256'] == sha(HERE / 'project.pds')
    assert report['run_project_sha256'] == sha(run / 'project.pds')
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True)
    assert result.returncode == 0
    save(HERE / 'artifacts/tasklist_final.csv', result.stdout)
    live = [line for line in result.stdout.splitlines() if re.match(rb'"(?:pds|pds_shell)\.exe"', line, re.I)]
    assert not live, live
    protected = protected_hashes()
    protected_initial = json.loads((HERE / 'compile_01/protected_before.json').read_bytes())
    assert all(protected.get(p) == h for p, h in protected_initial.items())
    sources = json.loads((run / 'inputs_before.json').read_bytes())
    assert all(sha(Path(p)) == h for p, h in sources.items())
    assert sources[str((HERE / 'inputs/source/top.v').resolve())] == TOP_HASH
    bindings = json.loads((HERE / 'artifacts/component_binding.json').read_bytes())
    for rel in COMPONENTS:
        assert sha(HERE.parent / rel) == sha(HERE / 'rtl' / Path(rel).name) == bindings[rel]
    write_json('artifacts/protected_hashes_final.json', {p: protected[p] for p in protected_initial})
    first = json.loads((HERE / 'compile_01/candidate_before.json').read_bytes())
    successful = json.loads((run / 'candidate_before.json').read_bytes())
    current_source_tree = {p.relative_to(HERE).as_posix(): sha(p) for p in HERE.rglob('*')
                           if p.is_file() and not p.is_relative_to(HERE / 'compile_01')}
    changes = {}
    for phase, old in [('initial_attempt_to_final', first), ('successful_attempt_to_final', successful)]:
        changed = {p: {'before': h, 'after': current_source_tree.get(p)} for p, h in old.items()
                   if current_source_tree.get(p) != h}
        assert not any(p.startswith(('rtl/', 'inputs/', 'baseline/')) for p in changed), changed
        changes[phase] = {'changed_files': changed,
                          'new_files': sorted(set(current_source_tree) - set(old)),
                          'allowed_change_scope': 'Candidate tooling/documentation/evidence; initial project timespec registration fix only'}
    assert not (run / 'place_route').exists() and not (run / 'device_map').exists()
    write_json('artifacts/final_verification.json', {
        'status': 'PASS_preliminary_candidate_only', 'compile_exit': 0, 'synthesis_exit': 0,
        'live_pds_processes': [], 'protected_files_unchanged': len(protected_initial),
        'run_source_frozen_hashes_unchanged': len(sources), 'component_sources_match_final_bindings': bindings,
        'candidate_top_sha256': report['candidate_top_sha256'],
        'candidate_pds_sha256': report['candidate_pds_sha256'],
        'run_project_sha256': report['run_project_sha256'],
        'whole_candidate_source_tree_changes': changes,
        'failed_initial_attempt_retained': True, 'pds_autoformat_limited_to_new_run_project': True,
        'no_pnr_device_map_ssh_board_ip_generation': True,
        'pending': report['pending'], 'timing_and_hardware_accepted': False,
    })
    # Includes run projects, logs, DB/netlist/reports and source copies. Exclude this
    # hash manifest alone to avoid a self-referential digest.
    all_files = {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(HERE.rglob('*'))
                 if p.is_file() and p != HERE / 'artifacts/all_candidate_final_sha256.json'}
    write_json('artifacts/all_candidate_final_sha256.json', all_files)
    print(f'Final audit PASS: {len(all_files)} candidate files hashed; {len(sources)} source/frozen and '
          f'{len(protected_initial)} protected files unchanged; no live PDS or PnR.')


if __name__ == '__main__':
    main()
