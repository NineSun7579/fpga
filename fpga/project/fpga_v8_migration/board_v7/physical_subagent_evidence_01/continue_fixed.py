"""Serial local implementation; archive first, validate actual CDC before PNR."""
from pathlib import Path
import subprocess, json, hashlib, shutil, re, time, traceback
BASE=Path(__file__).resolve().parent.parent
HERE=BASE/'source_diagnostics_route_02'
OUT=BASE/'physical_subagent_evidence_01'/'fixed_06'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v): (OUT/n).write_text(json.dumps(v,indent=2),encoding='utf8')
def busy():
    p=subprocess.run(['powershell','-NoProfile','-Command',"ConvertTo-Json -InputObject @(Get-Process | Where-Object { $_.ProcessName -match '^(pds|pds_shell|ta)$' } | Select-Object Id,ProcessName) -Compress"],capture_output=True,check=True)
    return json.loads(p.stdout)
def idle(): assert not busy(), 'PDS/TA busy; refusing concurrent launch'
def run(label,args,cwd):
    idle(); save(label+'_launch.json',{'command':args,'time':time.time()})
    print('START',label,flush=True)
    with (OUT/(label+'.log')).open('xb') as f:
        p=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/(label+'.log')).read_bytes()
    errors=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith(b'E:') or b'Timing-4003' in x]
    marks=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith(b'Process "') or x.startswith(b'Design ')]
    save(label+'_result.json',{'exit_code':p.returncode,'errors':errors,'marks':marks,'time':time.time()})
    assert p.returncode==0 and not errors,(label,p.returncode,errors)
    print('DONE',label,flush=True)
    return marks
def main():
    OUT.mkdir(exist_ok=True)
    print('Waiting for original controller and all PDS processes, no active project edits',flush=True)
    subprocess.run(['powershell','-NoProfile','-Command','Wait-Process -Id 5372,79684,40036 -ErrorAction SilentlyContinue'],capture_output=True)
    while busy(): time.sleep(10)
    archive=OUT/'standard_05_archive'
    if archive.exists():
        assert (OUT/'failure.txt').exists(), 'Existing attempt is not a failed preparation'
        shutil.move(str(archive),str(OUT/'first_preparation_archive'))
        shutil.move(str(OUT/'failure.txt'),str(OUT/'first_preparation_failure.txt'))
    archive.mkdir()
    for n in ['standard_flow.pds','run_native_physical.py','native_constraint_manifest.json','prepared_hashes.json','flow.log','run.log']:
        if (HERE/n).exists(): shutil.copy2(HERE/n,archive/n)
    for n in ['physical_standard_05','inputs','rtl','physical_constraints','compile','synthesize','synthesis_export','device_map','place_route']:
        if (HERE/n).exists(): shutil.copytree(HERE/n,archive/n)
    save('standard_05_archive_hashes.json',{str(p.relative_to(archive)):sha(p) for p in archive.rglob('*') if p.is_file()})
    guard=json.loads((BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    def check_guard():
        bad=[p for p,h in guard.items() if not Path(p).exists() or sha(Path(p))!=h]
        save('protection_check.json',{'count':len(guard),'mismatches':bad,'time':time.time()}); assert not bad,bad
    check_guard()
    inputs={str(p.relative_to(HERE)):sha(p) for n in ['inputs','rtl','physical_constraints'] for p in (HERE/n).rglob('*') if p.is_file()}
    save('input_hashes.json',inputs)
    raw=(archive/'standard_flow.pds').read_bytes()
    start=raw.index(b'(_command cmd_devmap'); end=raw.index(b'(_widget',start)
    block=raw[start:end]; opt=b'(_option top_module (_string "v7_sdt_top"))'
    assert block.count(opt)==1
    fixed=raw[:start]+block.replace(opt,b'')+raw[end:]
    assert re.findall(rb'\(_top_module[^\r\n]*',fixed)==re.findall(rb'\(_top_module[^\r\n]*',raw)
    compile_start=fixed.index(b'(_command cmd_compile')
    compile_end=fixed.index(b'(_command cmd_synthesize')
    assert opt in fixed[compile_start:compile_end], 'Preserve actual compile top identity'
    assert b'(_file "rtl/v7_sdt_top.v" + "v7_sdt_top:"' in fixed
    pnr=fixed[fixed.index(b'(_command cmd_pnr'):fixed.index(b'(_widget',fixed.index(b'(_command cmd_pnr'))]
    assert b'top_module' not in pnr
    save('correction.json',{'removed_only':opt.decode(),'before_sha256':sha(archive/'standard_flow.pds'),'after_sha256':hashlib.sha256(fixed).hexdigest(),'project_top_properties':[x.decode() for x in re.findall(rb'\(_top_module[^\r\n]*',fixed)],'pnr_top_module_present':False})
    # Outputs are archived; remove stale stage state by moving directories, never deleting protected sources.
    for n in ['compile','synthesize','device_map','place_route']:
        if (HERE/n).exists(): shutil.move(str(HERE/n),str(OUT/('pre_fixed_'+n)))
    fixed=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',fixed)
    project=HERE/'standard_flow_fixed.pds'; project.write_bytes(fixed)
    shutil.copy2(project,OUT/project.name)
    cmd=lambda stage:[str(PDS),'-project',str(project),'-run',stage,'-work_dir',str(HERE)]
    marks=run('synthesize',cmd('synthesize'),HERE)
    db=HERE/'synthesize/v7_sdt_top_syn.adf'; assert db.exists() and db.stat().st_size
    assert 'Process "Synthesize" started.' in marks and 'Process "Synthesize" done.' in marks
    export=OUT/'actual'; export.mkdir(); (export/'synthesis_export').mkdir(); (export/'analysis').mkdir()
    dump=export/'synthesis_export/synthesis_dump.txt'; script=OUT/'export_syn.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
    before=sha(db)
    run('export_synthesis',[str(PDS),'-file',str(script),'-work_dir',str(export),'-project_name','fixed06_actual'],export)
    assert sha(db)==before and dump.exists()
    for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','B_one_pair.sdc']:
        shutil.copy2(BASE/'source_diagnostics_route_01/actual'/n,export/'analysis'/n)
    for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py']:
        run(n[:-3],['python',str(export/'analysis'/n)],export)
    m=json.loads((export/'analysis/manifest.json').read_bytes()); exact=json.loads((export/'analysis/exact_complement.json').read_bytes())
    assert not m['errors'] and not exact['errors']
    prior=json.loads((HERE/'native_constraint_manifest.json').read_bytes())
    def native(pin):
        cell,port=pin.rsplit('/',1); return cell.replace('/','.')+'/'+port
    rows=[]
    for c,old in zip(exact['cameras'],prior['cameras']):
        pairs=sorted([native(a),native(b)] for a,b in c['bundle_pairs']); comp=sorted(native(p) for p in c['complement_launch_pins'])
        assert len(pairs)==320 and comp
        assert pairs==sorted(old['bundle_pairs']) and comp==sorted(old['complement_launch_pins']), 'New synthesis topology differs; regenerate constraints before mapping'
        rows.append({'camera':c['camera'],'pairs':len(pairs),'complement':len(comp)})
    assert sum(c['pairs'] for c in rows)==1280
    save('new_synthesis_validation.json',{'syn_sha256':before,'dump_sha256':sha(dump),'errors':[],'cameras':rows,'matches_native_fdc_mapping':True})
    for stage,path,mark in [('dev_map','device_map/v7_sdt_top_map.adf','Device Map'),('pnr','place_route/v7_sdt_top_pnr.adf','Place & Route')]:
        check_guard(); assert all(sha(HERE/p)==h for p,h in inputs.items())
        marks=run(stage,cmd(stage),HERE)
        artifact=HERE/path
        assert artifact.exists() and artifact.stat().st_size
        assert 'Process "'+mark+'" started.' in marks and 'Process "'+mark+'" done.' in marks
        assert any('successfully' in s for s in marks)
        save(stage+'_artifact.json',{'path':str(artifact),'sha256':sha(artifact)})
    check_guard()
    assert all(sha(HERE/p)==h for p,h in inputs.items())
    save('routed_acceptance_pending.json',{'routed_db':str(HERE/'place_route/v7_sdt_top_pnr.adf'),'ten_groups':False,'new_cdc':False,'io':False,'bit_permitted':False,'remote_or_program':False})
    print('REAL ROUTED DB COMPLETE; continue full ten-group + new CDC + IO audit before bit',flush=True)
if __name__=='__main__':
    try: main()
    except BaseException:
        if OUT.exists(): (OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
