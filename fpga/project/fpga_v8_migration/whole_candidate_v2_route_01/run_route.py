"""One fresh, isolated PDS -run pnr; never retry, generate IP, bitgen or board I/O."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
V2 = HERE.parent / 'whole_candidate_v2'
PROJECT = HERE.parents[1]
PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def processes(label):
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, check=True)
    (HERE / ('processes_' + label + '.csv')).write_bytes(result.stdout)
    live = [s for s in result.stdout.decode('ascii', 'backslashreplace').splitlines()
            if re.match(r'"(?:pds|pds_shell)\.exe"', s, re.I)]
    if live:
        raise RuntimeError('Global PDS instance blocker; no process killed: ' + repr(live))

def guards():
    # Reuse explicit protected path list, not an import that could modify old __pycache__.
    previous = json.loads((V2 / 'artifacts/protected_hashes_final.json').read_bytes())
    paths = {PROJECT / p for p in previous}
    paths.update(p for p in V2.rglob('*') if p.is_file())
    return {str(p.resolve()): sha(p) for p in sorted(paths)}

def inputs():
    return {p.relative_to(HERE).as_posix(): sha(p)
            for root in ['inputs', 'rtl'] for p in sorted((HERE / root).rglob('*')) if p.is_file()}

def binding(project):
    result = []
    frozen_paths = set(re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', (V2 / 'project.pds').read_bytes()))
    for raw in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project):
        rel = raw.decode('ascii')
        p = (HERE / rel).resolve()
        assert p.is_relative_to(HERE) and p.is_file(), rel
        if raw in frozen_paths:
            assert sha(p) == sha(V2 / rel), rel
            result.append({'registered_path': rel, 'resolved_local_path': str(p), 'sha256': sha(p)})
        else:
            assert rel.split('/')[0] in ['compile', 'synthesize', 'device_map', 'place_route'], rel
    actual_paths = set(re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project))
    assert frozen_paths <= actual_paths, 'Frozen source registration removed'
    return result

def prepare():
    assert not (HERE / 'preparation.json').exists(), 'Never overwrite existing preparation'
    processes('before_prepare')
    before = guards()
    save('protected_before.json', before)
    for name in ['inputs', 'rtl']:
        assert not (HERE / name).exists()
        shutil.copytree(V2 / name, HERE / name)
    project = (V2 / 'project.pds').read_bytes()
    assert b'(_option top_module (_string "fpga_v8_cooperative_top_v2"))' in project
    assert b'(_device PG2L100H)' in project
    assert b'(_option prj_work_dir (_string "."))' in project
    assert b'(_option prj_impl_dir (_string "."))' in project
    (HERE / 'project.pds').write_bytes(project)
    (HERE / 'project_before_pnr.pds').write_bytes(project)
    save('registered_sources_before.json', binding(project))
    frozen = inputs()
    save('inputs_before.json', frozen)
    assert before == guards(), 'External protected files changed during preparation'
    save('preparation.json', {
        'frozen_origin': str(V2), 'project_byte_identical_to_frozen_v2': True,
        'own_local_source_files': len(frozen),
        'input_files': sum(k.startswith('inputs/') for k in frozen),
        'rtl_files': sum(k.startswith('rtl/') for k in frozen),
        'fdc_hashes': {k: v for k, v in frozen.items() if k.lower().endswith('.fdc')},
        'protected_files': len(before), 'existing_v2_entire_tree_protected': True,
        'fresh_flow': True, 'reused_synthesis_snapshot': False,
        'core_clock_mhz': 131.25, 'constraint_or_rtl_changes': False,
        'top': 'fpga_v8_cooperative_top_v2', 'work_dir': str(HERE),
        'authorization': 'Parent explicitly authorizes isolated full compile/synth/device_map/PnR only',
        'no_bitgen_no_ipgen_no_ssh_no_board': True})
    print('Prepared own local bytes and exact registered bindings.', flush=True)

def run():
    assert (HERE / 'preparation.json').is_file()
    assert not (HERE / 'pnr_started.json').exists(), 'No automatic retry or overwrite'
    assert not any((HERE / p).exists() for p in ['compile', 'synthesize', 'device_map', 'place_route'])
    processes('before_pnr')
    before = json.loads((HERE / 'protected_before.json').read_bytes())
    assert before == guards(), 'Protected files changed before launch'
    frozen = inputs()
    assert frozen == json.loads((HERE / 'inputs_before.json').read_bytes())
    command = [str(PDS), '-project', str(HERE / 'project.pds'), '-run', 'pnr', '-work_dir', str(HERE)]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (HERE / 'pnr_shell.log').open('xb') as log:
        child = subprocess.Popen(command, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
        save('pnr_started.json', {'command': command, 'pid': child.pid, 'started_utc': started})
        print('Started fresh full flow PID', child.pid, 'command', command, flush=True)
        code = child.wait()
    after = guards()
    save('protected_after.json', after)
    changes = {p: {'before': h, 'after': after.get(p)} for p, h in before.items() if after.get(p) != h}
    save('protected_changes.json', changes)
    local_after = inputs()
    save('inputs_after.json', local_after)
    project = (HERE / 'project.pds').read_bytes()
    (HERE / 'project_after_pnr.pds').write_bytes(project)
    try:
        save('registered_sources_after.json', binding(project))
        binding_ok = True
    except Exception as exc:
        binding_ok = False
        save('registered_binding_error.json', {'error': repr(exc)})
    text = (HERE / 'pnr_shell.log').read_bytes()
    save('pnr_result.json', {
        'exit_code': code, 'started_utc': started,
        'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'command': command, 'shell_log_sha256': sha(HERE / 'pnr_shell.log'),
        'completion_lines': [s.decode('ascii', 'backslashreplace') for s in text.splitlines() if b'Process "' in s and b'done' in s],
        'error_lines': [s.decode('ascii', 'backslashreplace') for s in text.splitlines() if s.startswith(b'E:')],
        'protected_unchanged': not changes, 'local_sources_unchanged': frozen == local_after,
        'registered_bindings_verified': binding_ok,
        'timing_signoff': False, 'bitstream_generated_by_agent': False})
    print('PDS finished; exit=', code, 'protected changes=', len(changes), 'local unchanged=', frozen == local_after, flush=True)
    if code or changes or frozen != local_after or not binding_ok:
        sys.exit(1)

if __name__ == '__main__':
    {'prepare': prepare, 'run': run}[sys.argv[1]]()
