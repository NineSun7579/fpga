"""Isolated serial official flow; derive constraints from this build's real graphs."""
from pathlib import Path
import ctypes
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from preflight import HERE, BOARD, BASE, load, save, sha, require, verify, frozen_guard

PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
EVIDENCE = HERE / 'evidence'
TOOLS = HERE / 'analysis_tools'
ORIGIN = BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/actual/analysis'
PROJECT = HERE / 'project.pds'
PRIOR_SCRIPTS = {'run_map_audit14.py', 'resume_exact11.py', 'run_exact11.py',
                 'summarize_exact11.py', 'audit_fixed.py', 'run_stage_map13.py'}

def classify_processes(current, own_pid):
    """Only actual tools and named prior executors; pure observers cannot own a slot."""
    busy, observers = [], []
    for p in current:
        name = p['Name'].lower(); command = p.get('CommandLine') or ''
        if p['ProcessId'] == own_pid:
            continue
        if name in {'pds.exe', 'pds_shell.exe', 'ta.exe'}:
            busy.append(p)
            continue
        if p['ParentProcessId'] == own_pid:
            continue
        scripts = set(re.findall(r'([A-Za-z0-9_]+\.py)\b', command))
        executor = name in {'python.exe', 'pythonw.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'}
        self_wait = re.search(r'(?i)Wait-Process\b[^;\r\n]*\b' + str(own_pid) + r'\b', command)
        if self_wait:
            observers.append(p)
        elif executor and scripts & PRIOR_SCRIPTS and re.search(r'(?i)\bpython(?:\.exe)?\b|\\python(?:w)?\.exe', command):
            busy.append(p)
    return busy, observers

def record(name, value):
    path = EVIDENCE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=True) + '\n').encode('ascii'))

def status(phase, **extra):
    save('controller_status.json', {'phase': phase, 'pid': os.getpid(), 'time': time.time(),
                                   'remote_or_program': False, 'bitstream_allowed': False, **extra})
    print(phase, flush=True)

def processes():
    command = "ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, check=True)
    return json.loads(result.stdout or b'[]')

def wait_idle():
    last = None
    while True:
        current = processes()
        busy, observers = classify_processes(current, os.getpid())
        key = [p['ProcessId'] for p in busy]
        if key != last:
            record('queue_snapshot.json', {'busy': busy, 'self_dependent_observers_excluded': observers,
                   'prior_scripts': sorted(PRIOR_SCRIPTS), 'time': time.time()})
            status('WAITING_EXTERNAL_CONTROLLERS' if busy else 'TOOL_IDLE', busy_pids=key)
            last = key
        if not busy:
            return
        time.sleep(5)

def protected():
    guard = load(BOARD / 'source_diagnostics_route_01/build01_guard.json')
    bad = [p for p, expected in guard.items() if not Path(p).is_file() or sha(Path(p)) != expected]
    record('protected_latest.json', {'count': len(guard), 'mismatches': bad})
    require(len(guard) == 1022 and not bad, 'Production/IP/old V7 protection drift')
    frozen_guard()

def run(label, command, cwd):
    wait_idle()
    protected()
    require(not (EVIDENCE / (label + '.log')).exists(), 'Refuse overwrite actual run: ' + label)
    record(label + '_launch.json', {'command': command, 'time': time.time(), 'cwd': str(cwd)})
    status('RUNNING_' + label.upper(), log=str(EVIDENCE / (label + '.log')))
    with (EVIDENCE / (label + '.log')).open('xb') as log:
        result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    raw = (EVIDENCE / (label + '.log')).read_bytes()
    errors = [x.decode('ascii', 'backslashreplace') for x in raw.splitlines()
              if x.startswith(b'E:') or re.match(rb'\s*(?:\*\*\s*)?(?:ERROR|FATAL)\b', x) or b'Timing-4003' in x]
    marks = [x.decode('ascii', 'backslashreplace') for x in raw.splitlines() if x.startswith((b'Process "', b'Design '))]
    record(label + '_result.json', {'exit_code': result.returncode, 'errors': errors, 'marks': marks})
    protected()
    require(result.returncode == 0 and not errors, 'Actual tool failure: ' + label)
    return marks

def snapshot():
    return {str(p.relative_to(HERE)): sha(p) for n in ['rtl', 'inputs', 'constraints_candidate']
            for p in (HERE / n).rglob('*') if p.is_file()}

def setup():
    manifest = verify()
    require(manifest['decode_candidates_gate']['status'] == 'PASS', 'Decode candidates not integrated')
    require(not PROJECT.exists(), 'Project already exists; no overwrite')
    source = BOARD / 'source_diagnostics_route_03/physical_constraints_exact_11'
    dest = HERE / 'constraints_candidate'; dest.mkdir()
    receipts = {}
    for name in ['clock.fdc', 'cdc.fdc', 'ddr3.fdc', 'ov5640.fdc', 'pcie.fdc', 'sfp.fdc']:
        path = source / name
        require(path.is_file(), 'Candidate constraint absent: ' + name)
        if name != 'clock.fdc':
            require(path.read_bytes() == (BASE / 'physical_constraints_exact_09' / name).read_bytes(), 'Nonclock constraint changed')
        (dest / name).write_bytes(path.read_bytes())
        receipts[str(path)] = sha(path)
    # IP descriptor side-assets and frozen FDC identity for derivation, never generated guesses.
    frozen = load(BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json')
    for name, expected in frozen.items():
        if name.startswith('inputs\\') and name.endswith(('.fdc', '.pds')):
            require(sha(BASE / name) == expected, 'Frozen FDC asset drift')
            out = HERE / name; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((BASE / name).read_bytes())
            manifest['local_hashes'][name.replace('\\', '/')] = expected
    raw = (HERE / 'project_template.pds').read_bytes().replace(b'constraints_pending/', b'constraints_candidate/')
    raw = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', raw)
    PROJECT.write_bytes(raw)
    TOOLS.mkdir()
    scripts = ['parse_objects.py', 'resolve_manifest.py', 'derive_exact_complement.py', 'classify_paths.py', 'B_one_pair.sdc']
    for name in scripts:
        (TOOLS / name).write_bytes((ORIGIN / name).read_bytes())
    parser = (TOOLS / 'parse_objects.py').read_bytes()
    needle = b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER')}"
    require(parser.count(needle) == 1, 'Parser CDB insertion point changed')
    (TOOLS / 'parse_objects.py').write_bytes(parser.replace(needle, b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER'), 'cdb_entries':children(i,'CDBENTRY')}"))
    record('import_candidate_constraints.json', {'qualified': False, 'source_hashes': receipts,
           'generator': str(BOARD / 'physical_subagent_evidence_01/generate_exact11.py'),
           'generator_sha256': sha(BOARD / 'physical_subagent_evidence_01/generate_exact11.py'),
           'analysis_tools': {n: sha(TOOLS / n) for n in scripts}})
    manifest['constraint_candidate_imported'] = True
    save('manifest.json', manifest)
    record('input_hashes.json', snapshot())
    verify()

def stage(label, stage_name, folder, db, mark):
    before = snapshot()
    require(not (HERE / folder).exists(), 'Stage outputs already exist')
    marks = run(label, [str(PDS), '-project', str(PROJECT), '-run', stage_name, '-work_dir', str(HERE)], HERE)
    require('Process "' + mark + '" done.' in marks, 'Missing official stage completion: ' + label + repr(marks))
    artifact = HERE / folder / db
    require(artifact.is_file() and artifact.stat().st_size > 0, 'No real ADF')
    require(snapshot() == before, 'Stage mutated source inputs')
    native_db = HERE / folder / {'compile': 'cmr.db', 'synthesize': 'snr.db', 'dev_map': 'dmr.db', 'pnr': 'prr.db'}[stage_name]
    require(native_db.is_file() and native_db.stat().st_size > 0, 'Missing actual native DB')
    tree = ET.parse(native_db)
    if stage_name == 'synthesize':
        table = next(t for t in tree.getroot().iter('table') if t.get('id') == 'synthesize_check_timing_summary')
        checks = {r.findall('data')[0].text: r.findall('data')[1].text for r in table.findall('row')}
        record('synthesis_structural_gate.json', checks)
        require(all(checks[k] == '0' for k in ['loops', 'latchs', 'latch_loops', 'no_clock', 'unexpandable_clocks']), 'Synthesis structural timing gate failed')
    record(label + '_artifact.json', {'path': str(artifact), 'sha256': sha(artifact),
           'native_db': str(native_db), 'native_db_sha256': sha(native_db), 'error_count': 0,
           'zero_errors_basis': 'exit0 + official done + complete shell E/Error/Fatal scan + actual native XML DB/ADF'})
    return artifact

def export_graph(label, db, resolve):
    dest = EVIDENCE / label
    analysis = dest / 'analysis'; analysis.mkdir(parents=True)
    dump = dest / 'synthesis_export/synthesis_dump.txt'; dump.parent.mkdir()
    script = dest / 'export.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {' + db.as_posix() + '} -output {' + dump.as_posix() + '}\n').encode('ascii'))
    before = sha(db)
    run(label + '_export', [str(PDS), '-file', str(script), '-work_dir', str(dest), '-project_name', 'timing01_' + label], dest)
    require(sha(db) == before, 'Export mutated DB')
    scripts = ['parse_objects.py'] + (['resolve_manifest.py', 'derive_exact_complement.py', 'classify_paths.py'] if resolve else [])
    for name in scripts + ['B_one_pair.sdc']:
        (analysis / name).write_bytes((TOOLS / name).read_bytes())
    for name in scripts:
        result = subprocess.run([sys.executable, str(analysis / name)], cwd=analysis, capture_output=True)
        (analysis / (name + '.log')).write_bytes(result.stdout + result.stderr)
        require(result.returncode == 0, 'New graph derivation failed: ' + name)
    return load(analysis / 'graph.json'), analysis

def generator():
    path = BOARD / 'physical_subagent_evidence_01/generate_exact11.py'
    # Only pure traversal/universe functions; never invoke the old main or old-leaf assertions.
    code = path.read_text(encoding='utf8')
    pure = code[code.index('def native('):code.index('def main():')]
    scope = {'re': re}
    exec(compile(pure, str(path), 'exec'), scope)
    return scope

def derive(cg, sg, analysis):
    gen = generator()
    raw = (BASE / 'inputs/source/constraints/clock.fdc').read_bytes()
    clocks, groups, universe, carved = gen['frozen_universe'](raw)
    require(len(universe) == 368 and len(universe - carved) == 364, 'Frozen U cardinality mismatch')
    require(not any(a == b for a, b in universe), 'Same-domain exception')
    m = load(analysis / 'manifest.json'); exact = load(analysis / 'exact_complement.json')
    require(not m['errors'] and not exact['errors'] and len(m['resolved']) == 2048, 'Unresolved new mailbox graph')
    lines = ['# Derived from this build real compile/synthesis graphs, never old leaf equality.']
    for a, b in sorted(universe - carved):
        lines.append('set_false_path -from [get_clocks {' + a + '}] -to [get_clocks {' + b + '}]')
    rows = []; allpairs = set()
    for cam in range(4):
        cp = gen['camera_leaves'](cg, cam); sp = gen['camera_leaves'](sg, cam)
        pre = 'source_diagnostics/cameras[' + str(cam) + '].source/'
        mb = {k + '/' + p for k, r in cg['primitives'].items() if k.startswith(pre + 'mailbox[')
              for p, v in r['ports'].items() if v['clock']}
        host = {k + '/' + p for k, r in cg['primitives'].items() if k.startswith(pre + 'host_bank[')
                for p, v in r['ports'].items() if p.startswith('D[') and v['direction'] == 'INPUT'}
        require(len(mb) == 17 and len(host) == 512 and mb <= set(cp['leaves']), 'Compile mailbox contract changed')
        mapped = [r['mapping'] for r in m['resolved'] if r['camera'] == cam and r['mapping']['kind'] == 'register']
        pairs = {(r['launch_CLK'], r['capture_D']) for r in mapped}
        require(len(pairs) == 330, 'New mailbox physical pair count changed')
        sm = {a for a, b in pairs}; captures = {b for a, b in pairs}
        require(sm <= set(sp['leaves']), 'Mailbox launch omitted from clock traversal')
        comp = set(cp['leaves']) - mb; scomp = set(sp['leaves']) - sm
        # Direct single Q->D sinks establish exact B; no unrelated endpoints are budgeted.
        for a, b in pairs:
            q = a.rsplit('/', 1)[0] + '/Q'
            require(sg['pin_net'][q] == sg['pin_net'][b]
                    and set(sg['netpins'][sg['pin_net'][q]]) == {q, b}, 'Nonexclusive mailbox path')
        coll = gen['coll']
        lines += ['set_false_path -from ' + coll(comp | scomp) + ' -to [get_clocks {ddrphy_sysclk}]',
                  'set_max_delay -datapath_only 15.238 -from ' + coll(mb | sm) + ' -to ' + coll(host | captures),
                  'set_false_path -hold -from ' + coll(mb | sm) + ' -to ' + coll(host | captures)]
        ack, first, later = pre + 'ack', pre + 'ack_sync[0]', pre + 'ack_sync[1]'
        pn = sg['pin_net']
        require(pn[ack + '/Q'] == pn[first + '/D'] and pn[first + '/Q'] == pn[later + '/D']
                and pn[first + '/CLK'] == pn[later + '/CLK'] and pn[ack + '/CLK'] != pn[first + '/CLK'], 'ACK stages topology changed')
        lines.append('set_false_path -from ' + coll({ack + '/CLK'}) + ' -to ' + coll({first + '/D', pre + 'ack_sync[1:0]/D[0]'}))
        rows.append({'camera': cam, 'compile': cp, 'synthesis': sp, 'compile_mailbox': sorted(mb),
                     'compile_complement': sorted(comp), 'synthesis_complement': sorted(scomp),
                     'physical_pairs': sorted(pairs), 'ack_first': [ack + '/CLK', first + '/D'],
                     'ack_same_domain_later': [first + '/CLK', later + '/D']})
        allpairs |= pairs
    require(len(allpairs) == 1320, '1320 mapping gate failed')
    base = b'\n'.join(s for s in raw.splitlines() if not s.lstrip().startswith(b'set_clock_groups ')) + b'\n'
    generated = base + '\n'.join(lines).encode('ascii') + b'\n'
    dest = HERE / 'constraints_candidate/clock.fdc'
    (EVIDENCE / 'clock_imported_candidate.fdc').write_bytes(dest.read_bytes())
    dest.write_bytes(generated)
    proof = {'passed': True, 'method': 'new graph traversal and exhaustive LUT-cone mailbox resolution',
             'old_U': sorted(universe), 'retained_clock_pairs': sorted(universe - carved),
             'carved_camera_to_ddr': sorted(carved), 'same_domain_exemptions': [],
             'all_old_pairs_accounted': (universe - carved) | carved == universe,
             'mailbox_budget_ns': 15.238, 'physical_pairs': 1320, 'cameras': rows,
             'clocks': sorted(clocks), 'original_groups': groups, 'clock_fdc_sha256': sha(dest),
             'compile_graph_sha256': sha(EVIDENCE / 'compile/analysis/graph.json'),
             'synthesis_graph_sha256': sha(analysis / 'graph.json'), 'runtime_proven': False}
    record('coverageproof_new_graph.json', proof)
    record('input_hashes.json', snapshot())
    return proof

def runtime_constraints(proof, sg):
    path = BOARD / 'physical_subagent_evidence_01/summarize_exact11.py'
    text = path.read_text(encoding='utf8')
    scope = {'ET': ET}
    pure = text[text.index('def flatten('):text.index('def main():')]
    exec(compile(pure, str(path), 'exec'), scope)
    baseline = load(BOARD.parent / 'whole_candidate_v7_route_01/evidence/stage_tables.json')['synthesize']
    frozen_clocks = {r['data'][0] for r in scope['flatten'](baseline['synthesize_report_timing_clock_summary']['rows'])}
    require(frozen_clocks == set(proof['clocks']), 'Frozen actual clock universe mismatch')
    old_async = {tuple(r['data'][:2]) for r in baseline['synthesize_report_clock_interaction']['rows'] if r['data'][3] == 'Asynchronous Groups'}
    required = old_async - {tuple(p) for p in proof['carved_camera_to_ddr']}
    tables = scope['extract'](HERE / 'synthesize/snr.db')
    interactions = {tuple(r['data'][:2]): r['data'] for k, v in tables.items() if 'clock_interaction' in k for r in v['rows']}
    clocks = {r['data'][0] for k, v in tables.items() if 'clock_summary' in k for r in scope['flatten'](v['rows'])}
    missing = sorted(required - set(interactions))
    lost = [p for p in required & set(interactions) if 'False Path' not in interactions[p][3]]
    same = [v for (a, b), v in interactions.items() if a == b and 'False Path' in v[3]]
    record('runtime_clockpair_proof.json', {'tables': tables, 'clocks': sorted(clocks), 'missing': missing,
           'lost': lost, 'same_domain_false_exemptions': same, 'declared_U': 368,
           'retained': 364, 'supplemented_camera_relations': 4,
           'passed': bool(interactions) and not missing and not lost and not same and clocks == frozen_clocks})
    require(interactions and not missing and not lost and not same and clocks == frozen_clocks, 'Runtime U-B clockpair inheritance failed')
    # CDB provenance is saved for every new complement leaf; no old-leaf whitelist deletion.
    rows = []
    for camera in proof['cameras']:
        for pin in camera['synthesis_complement']:
            cell, port = pin.rsplit('/', 1)
            rows.append({'pin': pin, 'cdb_entries': sg['primitives'][cell].get('cdb_entries', [])})
    record('complement_cdb_provenance.json', {'rows': rows, 'clock_fdc_sha256': sha(HERE / 'constraints_candidate/clock.fdc')})

def main():
    EVIDENCE.mkdir(exist_ok=True)
    status('QUEUED_SERIAL_BUILD')
    wait_idle()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, True, 'Global\\ov56401_PDS_single_instance')
    require(handle and ctypes.get_last_error() != 183, 'Another cooperating PDS controller owns mutex')
    try:
        protected(); setup()
        comp = stage('compile', 'compile', 'compile', 'v7_sdt_top_comp.adf', 'Compile')
        syn = stage('synthesize', 'synthesize', 'synthesize', 'v7_sdt_top_syn.adf', 'Synthesize')
        cg, ca = export_graph('compile', comp, False)
        sg, sa = export_graph('actual', syn, True)
        proof = derive(cg, sg, sa)
        # Changing clock constraints invalidates prior synthesis: official dev_map may rerun it.
        mapped = stage('dev_map', 'dev_map', 'device_map', 'v7_sdt_top_map.adf', 'Device Map')
        new_comp, nca = export_graph('compile_post_constraints', HERE / 'compile/v7_sdt_top_comp.adf', False)
        new_syn, nsa = export_graph('actual_post_constraints', HERE / 'synthesize/v7_sdt_top_syn.adf', True)
        # Regenerate rather than blindly trust old nodes. PNR only if existing FDC exactly covers the new graph.
        old_clock = (HERE / 'constraints_candidate/clock.fdc').read_bytes()
        post = derive(new_comp, new_syn, nsa)
        require(old_clock == (HERE / 'constraints_candidate/clock.fdc').read_bytes(), 'Post-map synthesis changed names; new map attempt required before PNR')
        record('coverageproof_synthesis.json', post)
        runtime_constraints(post, new_syn)
        record('canonical_equivalence_after_remap.json', {'physical_pairs': 1320, 'verified_by': 'coverageproof_synthesis.json'})
        route = stage('pnr', 'pnr', 'place_route', 'v7_sdt_top_pnr.adf', 'Place & Route')
        record('pnr_artifact.json', {'path': str(route), 'sha256': sha(route)})
        from routed_acceptance import audit_all
        audit_all(route)
        from prepare_local_delivery import finish_local_delivery
        finish_local_delivery(route)
        status('PHYSICAL_SIGNOFF_AND_LOCAL_DELIVERY_PASS_NO_REMOTE_PROGRAM')
    finally:
        kernel.CloseHandle(handle)

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / 'failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        status('FAILED_EVIDENCE_PRESERVED', failure=str(EVIDENCE / 'failure.txt'))
        raise
