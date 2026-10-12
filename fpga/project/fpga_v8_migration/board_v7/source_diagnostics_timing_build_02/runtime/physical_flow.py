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
EVIDENCE = HERE / 'evidence/runtime'
TOOLS = Path(__file__).resolve().parent / 'analysis_tools'
ORIGIN = BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/actual/analysis'
PROJECT = HERE / 'project.pds'
PRIOR_SCRIPTS = {'run_map_audit14.py', 'resume_exact11.py', 'run_exact11.py',
                 'summarize_exact11.py', 'audit_fixed.py', 'run_stage_map13.py'}

def classify_processes(current, own_pid):
    """Only actual tools and named prior executors; pure observers cannot own a slot."""
    busy, observers = [], []
    bypid={p['ProcessId']:p for p in current}
    ancestors=set();parent=bypid.get(own_pid,{}).get('ParentProcessId')
    while parent and parent in bypid and parent not in ancestors:
        ancestors.add(parent);parent=bypid[parent].get('ParentProcessId')
    for p in current:
        name = p['Name'].lower(); command = p.get('CommandLine') or ''
        if p['ProcessId'] == own_pid:
            continue
        if name in {'pds.exe', 'pds_shell.exe', 'ta.exe'}:
            busy.append(p)
            continue
        if p['ProcessId'] in ancestors:
            observers.append(p)
            continue
        if p['ParentProcessId'] == own_pid:
            continue
        scripts = set(re.findall(r'([A-Za-z0-9_]+\.py)\b', command))
        normalized=command.replace('\\','/').lower()
        map_controller=bool(re.search(r"diagnostic_sync_register_map_01/(?:run|audit_final|recover)\.py(?:\s|[\"']|$)",normalized))
        build01_resume=bool(re.search(r"source_diagnostics_timing_build_01/resume_actual_graph\.py(?:\s|[\"']|$)",normalized))
        other_build02='source_diagnostics_timing_build_02/runtime/controller02.py' in normalized
        prior=scripts & (PRIOR_SCRIPTS | {'recover_compile_attempt.py','run_pds.py','finalize_exact11.py',
               'run_export_fdc17.py','run_mapped_timing15.py','resolve_mapped14.py','verify_routed11.py'})
        executor = name in {'python.exe', 'pythonw.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'}
        self_wait = re.search(r'(?i)Wait-Process\b[^;\r\n]*\b' + str(own_pid) + r'\b', command)
        if self_wait:
            observers.append(p)
        elif executor and (prior or map_controller or build01_resume or other_build02) and re.search(r'(?i)\bpython(?:\.exe)?\b|\\python(?:w)?\.exe', command):
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
    ledger=EVIDENCE/'runtime_hash_append.json'
    if ledger.exists():
        for name,expected in load(ledger)['runtime_hash_append'].items():
            require(sha(HERE/name)==expected,'Runtime hash drift: '+name)
    from controller02 import project_guard
    project_guard()

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
    record(label + '_result.json', {'exit_code': result.returncode, 'errors': errors, 'marks': marks,'log_sha256':sha(EVIDENCE/(label+'.log'))})
    protected()
    require(result.returncode == 0 and not errors, 'Actual tool failure: ' + label)
    return marks

def snapshot():
    return {str(p.relative_to(HERE)): sha(p) for n in ['rtl', 'inputs', 'constraints_live']
            for p in (HERE / n).rglob('*') if p.is_file()}

def setup():
    manifest = verify()
    require(manifest['decode_candidates_gate']['status'] == 'PASS', 'Decode candidates not integrated')
    require(not PROJECT.exists(), 'Project already exists; no overwrite')
    source = BOARD / 'source_diagnostics_timing_build_01/constraints_candidate'
    dest = HERE / 'constraints_live'; dest.mkdir()
    receipts = {}
    for name in ['clock.fdc', 'cdc.fdc', 'ddr3.fdc', 'ov5640.fdc', 'pcie.fdc', 'sfp.fdc']:
        path = source / name
        require(path.is_file(), 'Candidate constraint absent: ' + name)
        if name != 'clock.fdc':
            require(path.read_bytes() == (BASE / 'physical_constraints_exact_09' / name).read_bytes(), 'Nonclock constraint changed')
        (dest / name).write_bytes((HERE/'inputs/source/constraints/clock.fdc').read_bytes() if name=='clock.fdc' else path.read_bytes())
        receipts[str(path)] = sha(path)
    # All descriptor side-assets are already part of the immutable 741-file copy.
    raw = (HERE / 'project_template.pds').read_bytes().replace(b'constraints_pending/', b'constraints_live/')
    raw = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', raw)
    PROJECT.write_bytes(raw)
    scripts = [p.name for p in TOOLS.glob('*.py')]
    record('import_candidate_constraints.json', {'qualified': False, 'source_hashes': receipts,
           'generator': str(BOARD / 'physical_subagent_evidence_01/generate_exact11.py'),
           'generator_sha256': sha(BOARD / 'physical_subagent_evidence_01/generate_exact11.py'),
           'analysis_tools': {n: sha(TOOLS / n) for n in scripts}})
    record('hash_append_prepared.json',{'immutable_manifest_sha256':sha(HERE/'manifest.json'),
           'new_project_sha256':sha(PROJECT),'runtime_tools':{n:sha(TOOLS/n) for n in scripts},
           'inputs_preserved':True,'initial_clock':'frozen clocks only; no old leaf names'})
    record('input_hashes.json', snapshot())
    verify()

def official_stage_complete(stage_name,mark,marks):
    expected={'Device Map','DevMap'} if stage_name=='dev_map' else {mark}
    return any('Process "'+name+'" done.' in marks for name in expected)

def stage(label, stage_name, folder, db, mark):
    before = snapshot()
    require(not (HERE / folder).exists(), 'Stage outputs already exist')
    started=time.time()
    if stage_name=='dev_map':
        script=EVIDENCE/'map.tcl'
        script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nopen_project {'+PROJECT.as_posix()+'}\ndev_map -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n').encode('ascii'))
        command=[str(PDS),'-file',str(script),'-work_dir',str(HERE)]
    else:command=[str(PDS), '-project', str(PROJECT), '-run', stage_name, '-work_dir', str(HERE)]
    marks = run(label,command,HERE)
    require(official_stage_complete(stage_name,mark,marks), 'Missing official stage completion: '+label+repr(marks))
    artifact = HERE / folder / db
    require(artifact.is_file() and artifact.stat().st_size > 0 and artifact.stat().st_mtime>=started-2, 'No fresh real ADF; reject no-op')
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
    scripts = ['parse_objects.py'] + (['resolve_manifest.py', 'classify_paths.py'] if resolve else [])
    for name in scripts + ['graph_adapter.py','derive_new_constraints.py']:
        (analysis / name).write_bytes((TOOLS / name).read_bytes())
    for name in scripts:
        result = subprocess.run([sys.executable, str(analysis / name)], cwd=analysis, capture_output=True)
        (analysis / (name + '.log')).write_bytes(result.stdout + result.stderr)
        require(result.returncode == 0, 'New graph derivation failed: ' + name)
    graph=load(analysis/'graph.json')
    record(label+'_graph_artifact.json',{'source_adf_sha256':sha(db),'graph_sha256':sha(analysis/'graph.json'),
           'dump_sha256':sha(dump),'parser_sha256':sha(analysis/'parse_objects.py'),'resolve':resolve})
    return graph,analysis

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
    dest = HERE / 'constraints_live/clock.fdc'
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
    record('complement_cdb_provenance.json', {'rows': rows, 'clock_fdc_sha256': sha(HERE / 'constraints_live/clock.fdc')})

def derive(cg,sg,analysis):
    """Replace the reference derive with strict new-graph resolution, without old ACK-name fallback."""
    sys.path.insert(0,str(TOOLS))
    from derive_new_constraints import derive as derive_pure
    compiler=EVIDENCE/('compile_post_constraints' if (EVIDENCE/'compile_post_constraints/analysis/graph.json').exists() else 'compile')/'analysis/graph.json'
    require(load(compiler)==cg and load(analysis/'graph.json')==sg,'Derivation graph binding changed')
    raw,proof=derive_pure(compiler,analysis/'graph.json',analysis/'manifest.json',HERE/'inputs/source/constraints/clock.fdc')
    for row in proof['cameras']:
        launches={a for a,b in row['physical_pairs']}
        row['compile_complement']=sorted(set(row['compile']['leaves'])-set(row['compile_mailbox']))
        row['synthesis_complement']=sorted(set(row['synthesis']['leaves'])-launches)
    proof.update({'passed':proof['structural_pass'],'clocks':[re.search(rb'-name\s+\{([^}]+)\}',s)[1].decode('ascii')
                  for s in (HERE/'inputs/source/constraints/clock.fdc').read_bytes().splitlines() if s.startswith((b'create_clock ',b'create_generated_clock '))]})
    dest=HERE/'constraints_live/clock.fdc'
    record('constraint_revision_'+sha(dest)[:12]+'.json',{'before_sha256':sha(dest),'after_sha256':hashlib_sha(raw),
           'compile_graph_sha256':proof['compile_graph_sha256'],'synthesis_graph_sha256':proof['synthesis_graph_sha256']})
    dest.write_bytes(raw);proof['clock_fdc_sha256']=sha(dest)
    record('coverageproof_new_graph.json',proof);record('input_hashes.json',snapshot())
    return proof

def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()

def endpoint_audit(label,g,reference=None):
    """Reuse reviewed topology/parameter checks as pure code with ONLY build02 output sinks."""
    import collections,types
    src=BOARD/'diagnostic_sync_register_map_01/run.py'
    text=src.read_text(encoding='utf8');pure=text[text.index('def audit('):text.index('def main():')]
    scope={'collections':collections,'save':record};exec(compile(pure,str(src),'exec'),scope)
    a=scope['audit'](label,g,reference)
    detail_src=BOARD/'diagnostic_sync_register_map_01/audit_final.py'
    text=detail_src.read_text(encoding='utf8');pure=text[text.index('def parameters('):text.index('def main():')]
    detail_scope={'save':record};exec(compile(pure,str(detail_src),'exec'),detail_scope)
    d=detail_scope['detail'](label,g,a)
    # Full top roots differ from the small map wrapper. Re-evaluate against actual full-top aliases.
    for row in d['rows']:
        cam=row['camera'];chain=row['chain']
        expected=f'cmos{cam+1}_pclk' if chain in {'ack_sync','cr'} else 'ddrphy_sysclk'
        start=g['pin_net'][row['clock_endpoints'][0]];seen=set()
        def trace(net):
            if net in seen:return False
            seen.add(net)
            if any(x in {expected,'/@'+expected} or x.endswith('/@'+expected) for x in g['net_aliases'].get(net,[])):return True
            for pin in g['netpins'].get(net,[]):
                cell,p=pin.rsplit('/',1);rec=g['primitives'][cell]
                if rec['ports'][p]['direction']!='OUTPUT' or any(x in rec['type'].upper() for x in ['DFF','SRL','RAM','DRM']):continue
                for ip,v in rec['ports'].items():
                    if v['direction']=='INPUT' and cell+'/'+ip in g['pin_net'] and trace(g['pin_net'][cell+'/'+ip]):return True
            return False
        row['checks']['clock_root_connected']=trace(start)
        row['clock_root_expected']=expected
        row['all_proven_checks_passed']=all(row['checks'].values())
    d['failed_checks']=[{'logical':row['logical'],'checks':row['checks']} for row in d['rows'] if not row['all_proven_checks_passed']]
    record(label+'_endpoint_details.json',d)
    record(label+'_endpoint_audit_binding.json',{'topology_checker_sha256':sha(src),'parameter_checker_sha256':sha(detail_src),
           'clock_root_adapter':'full top cmos1..4 and ddrphy_sysclk; actual pin/net tracing',
           'pure_executed_sha256':hashlib_sha((pure).encode('utf8')),'output_root':str(EVIDENCE)})
    require(a['status']=='PASS' and not d['failed_checks'],'New actual graph endpoint/INIT/GRS/polarity audit failed: '+label)
    return a

def main():
    from controller02 import build
    return build()

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / 'failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        status('FAILED_EVIDENCE_PRESERVED', failure=str(EVIDENCE / 'failure.txt'))
        raise
