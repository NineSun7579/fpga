"""Test exact scalar FDC on an explicit fresh synthesis DB, in isolation."""
from pathlib import Path
import json,shutil,subprocess,hashlib,traceback
from native_query08 import BASE,PDS,idle
ROOT=BASE/'fixed_06'
SOURCE=ROOT/'synthesis_epoch10'
OUT=ROOT/'stage_map13'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    idle();OUT.mkdir(exist_ok=False)
    validation=json.loads((SOURCE/'topology_validated.json').read_bytes())
    original=SOURCE/'synthesize/v7_sdt_top_syn.adf'
    assert sha(original)==validation['synth_db_sha256'] and validation['pairs']==1280
    guard=json.loads((BASE.parent/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    assert all(sha(Path(p))==h for p,h in guard.items())
    db=OUT/'input_syn.adf';shutil.copy2(original,db)
    exact=json.loads((SOURCE/'actual/analysis/exact_complement.json').read_bytes())
    graph=json.loads((SOURCE/'actual/analysis/graph.json').read_bytes())
    assert not exact['errors']
    def coll(pins):
        assert pins
        for pin in pins:
            cell,port=pin.rsplit('/',1)
            assert cell in graph['primitives'] and port in graph['primitives'][cell]['ports'],pin
        def native(pin):
            cell,port=pin.rsplit('/',1);return cell.replace('/','.')+'/'+port
        return '[get_pins -hierarchical {'+' '.join(native(p) for p in sorted(set(pins)))+'}]'
    lines=['puts "STAGE_MAP13_EXACT_SCALAR_BEGIN"']
    rows=[]
    for c in exact['cameras']:
        assert len(c['bundle_pairs'])==320
        launches=c['mailbox_launch_pins'];captures=c['capture_D'];comp=c['complement_launch_pins']
        assert len(launches)==len(captures)==320 and not set(launches)&set(comp)
        lines+=['set_false_path -from '+coll(comp)+' -to [get_clocks {ddrphy_sysclk}]',
                'set_max_delay -datapath_only 15.238 -from '+coll(launches)+' -to '+coll(captures),
                'set_false_path -hold -from '+coll(launches)+' -to '+coll(captures)]
        rows.append({'camera':c['camera'],'pairs':320,'complement':len(comp)})
    fdc=[]
    for source in SOURCE.glob('*.fdc'):
        dest=OUT/source.name;data=source.read_bytes()
        if source.name=='clock.fdc':data+=('\n'+'\n'.join(lines)+'\n').encode('ascii')
        dest.write_bytes(data);fdc.append(dest)
    script=OUT/'map.tcl'
    text='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
    text+='\n'.join('add_constraint {'+p.as_posix()+'}' for p in sorted(fdc))+'\n'
    text+='dev_map -force_to_run -input_db_file {'+db.as_posix()+'}\n'
    script.write_text(text,encoding='ascii')
    cmd=[PDS,'-file',str(script),'-work_dir',str(OUT),'-project_name','stage_map13']
    before=sha(db)
    (OUT/'launch.json').write_text(json.dumps({'command':cmd,'input_db_sha256':before,'cameras':rows,'source_graph_sha256':sha(SOURCE/'actual/analysis/graph.json'),'pin_validation':'Exact exported synthesis graph membership; importer object count pending','bit_permitted':False},indent=2))
    idle()
    with (OUT/'shell.log').open('xb') as f:r=subprocess.run(cmd,cwd=OUT,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/'shell.log').read_bytes();text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    (OUT/'shell.txt').write_text(text,encoding='utf8')
    errors=[x for x in text.splitlines() if x.startswith('E:') or 'Timing-4003' in x]
    marks=[x for x in text.splitlines() if x.startswith(('Process "','Design '))]
    artifacts={str(p.relative_to(OUT)):sha(p) for p in (OUT/'device_map').glob('*.adf')}
    result={'exit_code':r.returncode,'errors':errors,'marks':marks,'mapped_artifacts':artifacts,'input_unchanged':sha(db)==before and sha(original)==before,'bit_permitted':False}
    (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
    assert result['input_unchanged']
    assert r.returncode==0 and not errors and artifacts,'Explicit stage input loading failed; preserve evidence'
    assert 'Process "Device Map" done.' in marks
    assert not any('Compile' in x or 'Synthesize' in x for x in marks),'Unexpected earlier stages'
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
