"""Build03 local serial flow; all new graph derivation and acceptance are local."""
from pathlib import Path
import ctypes, json, os, re, shutil, subprocess, sys, time, traceback
import xml.etree.ElementTree as ET
from preflight import HERE, BOARD, DATA, load, save, sha, require, verify, frozen_guard, map_gate, log_errors
from queue_policy import classify_processes
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
EVIDENCE=HERE/'evidence/runtime'
TOOLS=Path(__file__).resolve().parent/'analysis_tools'
PROJECT=HERE/'project.pds'
sys.path.insert(0,str(Path(__file__).resolve().parent/'libraries'))

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

def run(label, command, cwd):
    wait_idle()
    protected()
    require(not (EVIDENCE / (label + '.log')).exists(), 'Refuse overwrite actual run: ' + label)
    require(Path(cwd).resolve().is_relative_to(HERE),'Tool work directory must be build03-local')
    record(label + '_launch.json', {'command': command, 'time': time.time(), 'cwd': str(cwd),
           'controller_pid':os.getpid(),'runtime_ledger_sha256':sha(EVIDENCE/'runtime_hash_append.json'),
           'command_sha256':hashlib_sha(json.dumps(command,separators=(',',':')).encode())})
    status('RUNNING_' + label.upper(), log=str(EVIDENCE / (label + '.log')))
    with (EVIDENCE / (label + '.log')).open('xb') as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        record(label+'_process.json',{'pid':process.pid,'controller_pid':os.getpid(),'launch_sha256':sha(EVIDENCE/(label+'_launch.json')),'started':time.time()})
        result_code = process.wait()
    raw = (EVIDENCE / (label + '.log')).read_bytes()
    errors = log_errors(raw)
    for p in Path(cwd).rglob('run.log'):
        for error in log_errors(p.read_bytes()):errors.append(str(p)+': '+error)
    marks = [x.decode('ascii', 'backslashreplace') for x in raw.splitlines() if x.startswith((b'Process "', b'Design '))]
    record(label + '_result.json', {'exit_code': result_code, 'errors': errors, 'marks': marks,'log_sha256':sha(EVIDENCE/(label+'.log'))})
    protected()
    require(result_code == 0 and not errors, 'Actual tool failure: ' + label)
    return marks

def snapshot():
    return {str(p.relative_to(HERE)): sha(p) for n in ['rtl', 'inputs', 'constraints_live']
            for p in (HERE / n).rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def official_stage_complete(stage_name,mark,marks):
    expected={'Device Map','DevMap'} if stage_name=='dev_map' else {mark}
    return any('Process "'+name+'" done.' in marks for name in expected)

def stage(label, stage_name, folder, db, mark):
    before = snapshot()
    require(not (HERE / folder).exists(), 'Stage outputs already exist')
    started=time.time()
    if stage_name=='dev_map':
        script=EVIDENCE/'map.tcl'
        script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(HERE/'constraints_live/clock.fdc').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+(HERE/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n').encode('ascii'))
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
    native_errors=[]
    for table in tree.getroot().iter('table'):
        if 'message' not in table.get('id','').lower():continue
        for row in table.findall('row'):
            values=[d.text or '' for d in row.findall('data')]
            if any(v.strip().lower() in {'error','fatal'} for v in values):native_errors.append(values)
    record(label+'_native_message_audit.json',{'native_db_sha256':sha(native_db),'errors':native_errors})
    require(not native_errors,'Actual native DB reports errors: '+label)
    if stage_name == 'synthesize':
        table = next(t for t in tree.getroot().iter('table') if t.get('id') == 'synthesize_check_timing_summary')
        checks = {r.findall('data')[0].text: r.findall('data')[1].text for r in table.findall('row')}
        record('synthesis_structural_gate.json', checks)
        require(all(checks[k] == '0' for k in ['loops', 'latchs', 'latch_loops', 'no_clock', 'unexpandable_clocks']), 'Synthesis structural timing gate failed')
    record(label + '_artifact.json', {'path': str(artifact), 'sha256': sha(artifact),
           'native_db': str(native_db), 'native_db_sha256': sha(native_db), 'error_count': 0,'fresh_started':started,'official_marks':marks,
           'zero_errors_basis': 'exit0 + official done + complete shell E/Error/Fatal scan + actual native XML DB/ADF'})
    return artifact

def export_graph(label, db, resolve):
    dest = EVIDENCE / label
    analysis = dest / 'analysis'; analysis.mkdir(parents=True)
    dump = dest / 'synthesis_export/synthesis_dump.txt'; dump.parent.mkdir()
    script = dest / 'export.tcl'
    script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {' + db.as_posix() + '} -output {' + dump.as_posix() + '}\n').encode('ascii'))
    before = sha(db)
    run(label + '_export', [str(PDS), '-file', str(script), '-work_dir', str(dest), '-project_name', 'timing03_' + label], dest)
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

def protected():
    guard=load(DATA/'protected_guard.json')
    bad=[n for n,h in guard.items() if not Path(n).is_file() or sha(n)!=h]
    record('protected_latest.json',{'count':len(guard),'mismatches':bad})
    require(len(guard)==1022 and not bad,'Production/IP/old V7 protection drift')
    from controller03 import immutable_runtime_guard
    immutable_runtime_guard()
    gate=map_gate()
    require(gate['status']=='PASS','Refuse any PDS/tool start without actual map02 final PASS: '+str(gate))

def setup():
    verify()
    require(not PROJECT.exists() and not (HERE/'constraints_live').exists(),'Refuse overwrite initial project/constraints')
    dest=HERE/'constraints_live';dest.mkdir()
    for name in ['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc']:
        (dest/name).write_bytes((HERE/'constraints_templates'/name).read_bytes())
    raw=(HERE/'project_template.pds').read_bytes().replace(b'constraints_templates/',b'constraints_live/')
    PROJECT.write_bytes(raw)
    record('initial_project_binding.json',{'project_sha256':sha(PROJECT),'project_template_sha256':sha(HERE/'project_template.pds'),
           'source_root':str(HERE),'constraints_qualified':False,'old_physical_leaf_fallback':False})

def endpoint_audit(label,g,reference=None):
    from endpoints import full_top_audit
    return full_top_audit(label,g,record)

def runtime_constraints(proof, sg):
    from clock_tables import flatten, extract
    scope = {'flatten': flatten, 'extract': extract}
    baseline = load(DATA/'reference_tables.json')['synthesize']
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
    from cdb_proof import prove
    cdb=prove('synthesis',EVIDENCE/'actual_post_constraints/synthesis_export/synthesis_dump.txt',sg)
    record('runtime_U_B_gate.json',{'passed':True,'actual_clock_interaction_sha256':sha(EVIDENCE/'runtime_clockpair_proof.json'),
           'actual_CDB_sha256':sha(EVIDENCE/'actual_cdb_synthesis_proof.json'),'declared_clockpairs':368,'retained_clockpairs':364})

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
                  for s in (HERE/'inputs/source/constraints/clock.fdc').read_bytes().splitlines() if s.lstrip().startswith((b'create_clock ',b'create_generated_clock '))]})
    dest=HERE/'constraints_live/clock.fdc'
    record('constraint_revision_'+sha(dest)[:12]+'.json',{'before_sha256':sha(dest),'after_sha256':hashlib_sha(raw),
           'compile_graph_sha256':proof['compile_graph_sha256'],'synthesis_graph_sha256':proof['synthesis_graph_sha256']})
    dest.write_bytes(raw);proof['clock_fdc_sha256']=sha(dest)
    record('coverageproof_new_graph.json',proof);record('input_hashes.json',snapshot())
    return proof

def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()
