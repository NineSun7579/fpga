"""Independent synthesis topology control, no map/PNR/bit acceptance."""
from pathlib import Path
import json, subprocess, hashlib, shutil, traceback, re
from native_query08 import BASE, PDS, idle
from prepare_query_epoch08 import main as prepare

OUT=BASE/'fixed_06/synthesis_epoch10'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,cmd,cwd,required=()):
    idle()
    (OUT/(label+'_launch.json')).write_text(json.dumps({'command':cmd},indent=2))
    with (OUT/(label+'.log')).open('xb') as f:
        r=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/(label+'.log')).read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    errors=[x for x in text.splitlines() if x.startswith('E:') or 'Timing-4003' in x]
    marks=[x for x in text.splitlines() if x.startswith(('Process "','Design '))]
    (OUT/(label+'_result.json')).write_text(json.dumps({'exit_code':r.returncode,'errors':errors,'marks':marks},indent=2))
    assert r.returncode==0 and not errors,(label,errors)
    assert all(x in text for x in required),(label,required)
    print(label,'DONE',flush=True)

def main():
    idle()
    guard=json.loads((BASE.parent/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    def check():
        bad=[p for p,h in guard.items() if not Path(p).exists() or sha(Path(p))!=h]
        assert not bad,bad
    check()
    prepare(OUT,BASE/'synthesis_epoch10_tail.fdc')
    # A fresh compile/synthesis; copied query compile is archived, never seeded as success.
    shutil.move(str(OUT/'compile'),str(OUT/'copied_compile_archive'))
    project=OUT/'query_epoch08.pds'
    raw=project.read_bytes()
    raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
    project.write_bytes(raw)
    clock=OUT/'clock.fdc'
    assert b'set_max_delay' not in clock.read_bytes() and b'mailbox[' not in clock.read_bytes()
    inputs={str(p):sha(p) for p in OUT.glob('*.fdc')}
    (OUT/'control_identity.json').write_text(json.dumps({'fdc_hashes':inputs,'protected_count':len(guard),'purpose':'No mailbox compile constraints; regenerate 1280 pairs before post-synthesis loading','map_permitted':False,'bit_permitted':False},indent=2))
    run('synthesize',[PDS,'-project',str(project),'-run','synthesize','-work_dir',str(OUT)],OUT,
        ['Process "Compile" done.','Process "Synthesize" done.','has been successfully synthesized'])
    db=OUT/'synthesize/v7_sdt_top_syn.adf'; before=sha(db)
    actual=OUT/'actual'; (actual/'synthesis_export').mkdir(parents=True); (actual/'analysis').mkdir()
    script=actual/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+(actual/'synthesis_export/synthesis_dump.txt').as_posix()+'}\n',encoding='ascii')
    run('export_syn',[PDS,'-file',str(script),'-work_dir',str(actual),'-project_name','synthesis_epoch10_export'],actual)
    assert sha(db)==before
    origin=BASE.parent/'source_diagnostics_route_01/actual'
    for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py','B_one_pair.sdc']:
        shutil.copy2(origin/n,actual/'analysis'/n)
    for n in ['parse_objects','resolve_manifest','derive_exact_complement','classify_paths']:
        run(n,['python',str(actual/'analysis'/(n+'.py'))],actual)
    m=json.loads((actual/'analysis/manifest.json').read_bytes());e=json.loads((actual/'analysis/exact_complement.json').read_bytes())
    assert not m['errors'] and not e['errors']
    assert sum(len(c['bundle_pairs']) for c in e['cameras'])==1280
    assert [len(c['complement_launch_pins']) for c in e['cameras']]==[748,748,755,755]
    check(); assert all(sha(Path(p))==h for p,h in inputs.items())
    (OUT/'topology_validated.json').write_text(json.dumps({'synth_db_sha256':before,'pairs':1280,'complements':[748,748,755,755],'protected_unchanged':True,'constraint_load_pending':True,'pnr_permitted':False,'bit_permitted':False},indent=2))
    print('1280-pair fresh synthesis topology validated; stage constraint load pending',flush=True)

if __name__=='__main__':
    try: main()
    except BaseException:
        if OUT.exists(): (OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
