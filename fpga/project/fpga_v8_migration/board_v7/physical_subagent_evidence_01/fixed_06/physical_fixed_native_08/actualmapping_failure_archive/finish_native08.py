"""Wait for actual map, revalidate any new synthesis, finish PNR and local gates."""
from pathlib import Path
import subprocess,sys,json,shutil,traceback
import continue_fixed as cf
from run_native_fixed08 import OUT,ROOT,HERE,PDS,sha,launch
cf.OUT=OUT
def main():
    subprocess.run(['powershell','-NoProfile','-Command','Wait-Process -Id 37960 -ErrorAction SilentlyContinue'],capture_output=True)
    assert (OUT/'dev_map_artifact.json').exists(), 'Actual map failed; inspect dev_map_result.json, never proceed on exit0 alone'
    if not (OUT/'pnr_artifact.json').exists():
        cf.idle();actual=OUT/'actual';(actual/'analysis').mkdir(parents=True);(actual/'synthesis_export').mkdir()
        db=HERE/'synthesize/v7_sdt_top_syn.adf';h=sha(db);dump=actual/'synthesis_export/synthesis_dump.txt';script=actual/'export.tcl'
        script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',encoding='ascii')
        cf.run('export_new_syn',[str(PDS),'-file',str(script),'-work_dir',str(actual),'-project_name','native08_syn_graph'],actual)
        assert sha(db)==h
        origin=ROOT/'native_probe_07/synthesize_actual/analysis'
        for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py','B_one_pair.sdc']:shutil.copy2(origin/n,actual/'analysis'/n)
        for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py']:cf.run('new_'+n[:-3],['python',str(actual/'analysis'/n)],actual)
        exact=json.loads((actual/'analysis/exact_complement.json').read_bytes());previous=json.loads((origin/'exact_complement.json').read_bytes());manifest=json.loads((actual/'analysis/manifest.json').read_bytes())
        assert not exact['errors'] and not manifest['errors']
        for a,b in zip(exact['cameras'],previous['cameras']):
            assert len(a['bundle_pairs'])==320 and a['complement_launch_pins']
            assert sorted(a['bundle_pairs'])==sorted(b['bundle_pairs']) and sorted(a['complement_launch_pins'])==sorted(b['complement_launch_pins'])
        cf.save('new_syn_validated.json',{'sha256':h,'pairs':1280,'complements':[len(c['complement_launch_pins']) for c in exact['cameras']],'matches_phase_aware_fdc':True})
        inputs=json.loads((OUT/'input_hashes.json').read_bytes());guard=json.loads((cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
        assert all(sha(HERE/p)==h for p,h in inputs.items()) and all(sha(Path(p))==h for p,h in guard.items())
        marks=launch('pnr');route=HERE/'place_route/v7_sdt_top_pnr.adf'
        assert route.exists() and route.stat().st_size and 'Process "Place & Route" started.' in marks and 'Process "Place & Route" done.' in marks
        assert any('successfully' in s for s in marks)
        cf.save('pnr_artifact.json',{'path':str(route),'sha256':sha(route)})
    cf.idle()
    result=subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('audit_fixed.py'))])
    assert result.returncode==0,'Local acceptance gates not passed; no bit permission'
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'finish_failure.txt').write_text(traceback.format_exc())
        raise
