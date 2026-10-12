"""Only the authorized isolated compile_01 PDS run; no PnR, IP generation or board I/O."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys
from build_candidate import HERE, BASE, TOP_NAME, COMPONENTS, COMPLETION, write_json, protected_hashes, copy_immutable

RUN_ROOT = HERE / 'compile_01'
RUN = RUN_ROOT
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')


def run_json(name, data):
    write_json((RUN / name).relative_to(HERE).as_posix(), data)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs_snapshot():
    files = list((HERE / 'inputs').rglob('*')) + list((BASE / 'inputs').rglob('*'))
    files += list((HERE / 'rtl').glob('*')) + [HERE / 'project.pds', BASE / 'project.pds', BASE / 'input_sha256.json']
    return {str(p.resolve()): sha(p) for p in sorted(set(files)) if p.is_file()}


def all_candidate_snapshot():
    # Excludes run outputs and the snapshot artifact itself; source snapshots stay complete.
    return {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(HERE.rglob('*'))
            if p.is_file() and not p.is_relative_to(RUN_ROOT) and '/pds_snapshots/' not in p.as_posix()}


def process_check(name):
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True)
    (RUN / f'processes_{name}.csv').write_bytes(result.stdout)
    text = result.stdout.decode('ascii', 'backslashreplace')
    live = [line for line in text.splitlines() if re.match(r'"(?:pds|pds_shell)\.exe"', line, re.I)]
    if live:
        raise RuntimeError('PDS single-instance guard: ' + '\n'.join(live))
    return live


def prepare():
    assert not RUN.exists(), 'Fresh run already exists; no cleanup or overwrite allowed'
    RUN.mkdir(parents=True)
    process_check('before_prepare')
    receipt = HERE.parent / 'capture_arm_contract/endpoint/artifacts/results.json'
    data = json.loads(receipt.read_bytes())
    assert data['status'] == 'PASS' and data['operations'] == 499 and data['events'] == 4288
    bindings = {}
    for rel in COMPONENTS:
        source, local = HERE.parent / rel, HERE / 'rtl' / Path(rel).name
        assert sha(source) == sha(local), f'Final component binding changed: {rel}'
        bindings[rel] = sha(local)
    copy_immutable(receipt, RUN / 'capture_endpoint_results.json')
    write_json('artifacts/capture_endpoint_completion.json', {
        'status': 'received_and_source_hash_verified', 'operations': 499, 'events': 4288,
        'receipt_sha256': sha(receipt), 'source_bindings': bindings,
        'authorization': 'Parent release of compile hold; isolated compile and optional synthesis only; no PnR or board',
    })
    protected = protected_hashes()
    run_json('protected_before.json', protected)
    run_json('inputs_before.json', inputs_snapshot())
    run_json('candidate_before.json', all_candidate_snapshot())
    project = (HERE / 'project.pds').read_bytes()
    assert project.count(b'(_device PG2L100H)') == 1
    assert b'(_option top_module (_string "' + TOP_NAME.encode() + b'"))' in project
    # New run project references immutable candidate files one directory above.
    prefix = ('../' * len(RUN.relative_to(HERE).parts)).encode('ascii')
    project = project.replace(b'"inputs/', b'"' + prefix + b'inputs/').replace(b'"rtl/', b'"' + prefix + b'rtl/')
    for rel in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project):
        target = (RUN / rel.decode('ascii')).resolve()
        assert target.is_relative_to(HERE) and target.is_file(), rel
    (RUN / 'project.pds').write_bytes(project)
    run_json('preparation.json', {
        'prepared_utc': datetime.now(timezone.utc).isoformat(), 'part': 'PG2L100H-6FBG484',
        'top_module': TOP_NAME, 'run_project_sha256': sha(RUN / 'project.pds'),
        'candidate_project_sha256': sha(HERE / 'project.pds'),
        'candidate_top_sha256': sha(HERE / f'rtl/{TOP_NAME}.v'),
        'source_bindings': bindings, 'paths_local_to_candidate': True,
        'core_clock_mhz': 25 * 84 / 16, 'core_clock_period_ns': 40 * 16 / 84,
        'clock_constraints_changed': False, 'preliminary_only': True,
        'pending': ['Independent reset domains, physical input identity, RX allocation and F2H retirement unresolved',
                    'Endpoint mapped eligibility warning validation pending in parent',
                    'No whole-design mapped simulation, timing closure or hardware acceptance'],
    })
    print(f'Prepared fresh {RUN}; capture endpoint final hashes match.')


def run(action):
    assert action in ['compile', 'synthesize'] and COMPLETION.is_file()
    assert RUN.is_dir() and (RUN / 'project.pds').is_file()
    if action == 'synthesize':
        compile_receipt = json.loads((RUN / 'compile_result.json').read_bytes())
        assert compile_receipt['pass'], 'Compile must pass before synthesis'
    result_path = RUN / f'{action}_result.json'
    log_path = RUN / f'{action}_shell.log'
    assert not result_path.exists() and not log_path.exists(), 'Never overwrite a completed/failed run'
    process_check(f'before_{action}')
    before = inputs_snapshot()
    old_project = (RUN / 'project.pds').read_bytes()
    command = [str(PDS), '-project', str(RUN / 'project.pds'), '-run', action, '-work_dir', str(RUN)]
    started = datetime.now(timezone.utc).isoformat()
    with log_path.open('wb') as log:
        child = subprocess.Popen(command, cwd=RUN, stdout=log, stderr=subprocess.STDOUT)
        run_json(f'{action}_started.json', {'command': command, 'pid': child.pid, 'started_utc': started})
        code = child.wait()
    process_check(f'after_{action}')
    after = inputs_snapshot()
    assert before == after, 'PDS changed immutable candidate or frozen input'
    text = log_path.read_bytes()
    expected = b'Process "Compile" done.' if action == 'compile' else b'Process "Synthesize" done.'
    passed = code == 0 and expected in text and not re.search(rb'(?m)^E:', text)
    current_project = (RUN / 'project.pds').read_bytes()
    (RUN / f'project_before_{action}.pds').write_bytes(old_project)
    (RUN / f'project_after_{action}.pds').write_bytes(current_project)
    run_json(f'{action}_result.json', {
        'action': action, 'command': command, 'started_utc': started,
        'finished_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': code, 'pass': passed,
        'completion_marker_found': expected in text, 'shell_log_sha256': sha(log_path),
        'run_project_before_sha256': hashlib.sha256(old_project).hexdigest(),
        'run_project_after_sha256': hashlib.sha256(current_project).hexdigest(),
        'run_project_autorewrite': old_project != current_project,
        'source_inputs_unchanged': True, 'immutable_input_files': len(after), 'preliminary_only': True,
    })
    run_json(f'inputs_after_{action}.json', after)
    protected = protected_hashes()
    protected_before = json.loads((RUN / 'protected_before.json').read_bytes())
    changed = {path: {'before': h, 'after': protected.get(path)} for path, h in protected_before.items()
               if protected.get(path) != h}
    assert not changed, changed
    run_json(f'protected_after_{action}.json', {p: protected[p] for p in protected_before})
    run_json(f'candidate_after_{action}.json', all_candidate_snapshot())
    print(f'{action}: exit={code} pass={passed}; source/frozen/protected hashes unchanged.')
    if not passed:
        print(text[-12000:].decode('ascii', 'backslashreplace'))
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Usage: run_pds.py prepare|compile|synthesize [attempt_NN]')
    if len(sys.argv) == 3:
        assert re.fullmatch(r'attempt_[0-9]{2}', sys.argv[2]), 'Invalid isolated attempt name'
        RUN = RUN_ROOT / sys.argv[2]
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        run(sys.argv[1])
