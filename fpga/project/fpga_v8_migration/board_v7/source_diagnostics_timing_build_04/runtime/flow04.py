from controller04 import *
import xml.etree.ElementTree as ET
EVIDENCE=E
TOOLS=RUNTIME/'analysis_tools'
PROJECT=HERE/'project.pds'
record=save
run=tool
def snapshot():
    return {str(p.relative_to(HERE)): sha(p) for n in ['rtl', 'inputs', 'constraints_live']
            for p in (HERE / n).rglob('*') if p.is_file() and '__pycache__' not in p.parts}

def official_stage_complete(stage_name,mark,marks):
    expected={'Device Map','DevMap'} if stage_name=='dev_map' else {mark}
    return any('Process "'+name+'" done.' in marks for name in expected)

def stage(label, stage_name, folder, db, mark):
    require(stage_name in {'compile','synthesize'}, 'Only compile/synthesis authorized')
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

def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()
