"""Constrain every retained physical mailbox duplicate; prove canonical 1280 classes."""
from pathlib import Path
import json,shutil,re,subprocess,traceback,hashlib
import continue_fixed as cf
BASE=cf.BASE;HERE=cf.HERE;PDS=cf.PDS;sha=cf.sha
ROOT=Path(__file__).resolve().parent/'fixed_06'
OUT=ROOT/'physical_exact_09'
def proof(analysis,oldanalysis):
    g=json.loads((analysis/'graph.json').read_bytes());m=json.loads((analysis/'manifest.json').read_bytes());old=json.loads((oldanalysis/'manifest.json').read_bytes())
    assert not m['errors'] and not old['errors'];lookup={(r['camera'],r['logical_bit']):r['mapping'] for r in old['resolved']}
    evidence=[];classes=set();actual=set()
    for r in m['resolved']:
        a=lookup[(r['camera'],r['logical_bit'])];b=r['mapping'];assert a['kind']==b['kind']
        if b['kind']!='register':continue
        classes.add((a['launch_CLK'],a['capture_D']));actual.add((b['launch_CLK'],b['capture_D']))
        if a['launch_CLK']==b['launch_CLK'] and a['capture_D']==b['capture_D']:continue
        rec={'camera':r['camera'],'logical_bit':r['logical_bit'],'canonical_pair':[a['launch_CLK'],a['capture_D']],'retained_pair':[b['launch_CLK'],b['capture_D']]}
        for key in ['launch_cell','capture_cell']:
            x=a[key];y=b[key];px=g['primitives'][x];py=g['primitives'][y]
            assert px['type']==py['type'] and px['parameters']==py['parameters'] and px['default_parameters']==py['default_parameters']
            assert px['ports']==py['ports']
            for port,v in px['ports'].items():
                if v['direction']!='INPUT':continue
                nx=g['pin_net'].get(x+'/'+port);ny=g['pin_net'].get(y+'/'+port)
                if key=='capture_cell' and port=='D':
                    assert nx==g['pin_net'][a['launch_cell']+'/Q'] and ny==g['pin_net'][b['launch_cell']+'/Q']
                else:assert nx==ny,(x,y,port)
        evidence.append(rec)
    assert len(classes)==1280 and len(actual)==1320 and len(evidence)==40
    return {'canonical_pairs':1280,'actual_physical_pairs':1320,'duplicate_equivalence_proofs':evidence,'no_unchecked_physical_pair':True}
def main():
    cf.idle();OUT.mkdir();cf.OUT=OUT
    analysis=OUT/'actual/analysis';analysis.mkdir(parents=True);(OUT/'actual/synthesis_export').mkdir()
    origin=ROOT/'physical_fixed_native_08/actual/analysis';baseline=ROOT/'native_probe_07/synthesize_actual/analysis'
    for n in ['graph.json','objects.json','manifest.json','parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py','B_one_pair.sdc']:shutil.copy2(origin/n,analysis/n)
    result=proof(analysis,baseline);cf.save('canonical_equivalence.json',result)
    p=analysis/'derive_exact_complement.py';raw=p.read_bytes();assert raw.count(b'assert len(pairs)==320')==1
    raw=raw.replace(b'assert len(pairs)==320',b'assert len(pairs)==330');p.write_bytes(raw)
    cf.run('derive_all_physical_pairs',['python',str(p)],analysis)
    exact=json.loads((analysis/'exact_complement.json').read_bytes());assert not exact['errors']
    native=ROOT/'physical_fixed_native_08/native_phase_mapping.json';phase=json.loads(native.read_bytes())
    constraints=HERE/'physical_constraints_exact_09';constraints.mkdir()
    def native(pin):cell,port=pin.rsplit('/',1);return cell.replace('/','.')+'/'+port
    def coll(pins):assert pins;return '[get_pins -hierarchical {'+' '.join(native(x) for x in sorted(set(pins)))+'}]'
    cg=json.loads((ROOT/'native_probe_07/compile_actual/analysis/graph.json').read_bytes())
    lines=[]
    for c,ph in zip(exact['cameras'],phase['cameras']):
        launches=set(c['mailbox_launch_pins'])|set(ph['compile_mailbox_clock_pins']);complement=set(c['complement_launch_pins'])|set(ph['compile_complement_clock_pins'])
        captures=set(c['capture_D']);pre=f"source_diagnostics/cameras[{c['camera']}].source/"
        for ip,r in cg['primitives'].items():
            if ip.startswith(pre+'host_bank['):captures.update(ip+'/'+port for port in r['ports'] if port.startswith('D['))
        assert len(c['bundle_pairs'])==330 and c['complement_launch_pins']
        lines+=['set_false_path -from '+coll(complement)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(launches)+' -to '+coll(captures),'set_false_path -hold -from '+coll(launches)+' -to '+coll(captures)]
    for p in (HERE/'physical_constraints_native_08').glob('*.fdc'):
        raw=p.read_bytes()
        if p.name=='clock.fdc':raw=raw.split(b'# Exact real-object CDC complement and mailbox absolute budget')[0]+b'# Exact real-object CDC complement and mailbox absolute budget\n'+'\n'.join(lines).encode('ascii')+b'\n'
        (constraints/p.name).write_bytes(raw)
    project=HERE/'standard_flow_exact09.pds';raw=(HERE/'standard_flow_fixed_native.pds').read_bytes();raw=raw.replace(b'physical_constraints_native_08/',b'physical_constraints_exact_09/');project.write_bytes(raw);shutil.copy2(project,OUT/project.name)
    inputs={str(p.relative_to(HERE)):sha(p) for n in ['inputs','rtl','physical_constraints','physical_constraints_native_08','physical_constraints_exact_09'] for p in (HERE/n).rglob('*') if p.is_file()};cf.save('input_hashes.json',inputs)
    guard=json.loads((BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    def check():assert all(sha(HERE/p)==h for p,h in inputs.items()) and all(sha(Path(p))==h for p,h in guard.items())
    check()
    cmd=lambda stage:[str(PDS),'-project',str(project),'-run',stage,'-work_dir',str(HERE)]
    marks=cf.run('dev_map',cmd('dev_map'),HERE);db=HERE/'device_map/v7_sdt_top_map.adf'
    assert db.exists() and db.stat().st_size and 'Process "Device Map" started.' in marks and 'Process "Device Map" done.' in marks
    cf.save('dev_map_artifact.json',{'path':str(db),'sha256':sha(db)})
    syn=HERE/'synthesize/v7_sdt_top_syn.adf';h=sha(syn);dump=OUT/'actual/synthesis_export/synthesis_dump.txt';script=OUT/'actual/export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+syn.as_posix()+'} -output {'+dump.as_posix()+'}\n')
    cf.run('export_new_syn',[str(PDS),'-file',str(script),'-work_dir',str(OUT/'actual'),'-project_name','exact09_syn'],OUT/'actual');assert sha(syn)==h
    previous=json.loads((analysis/'exact_complement.json').read_bytes())
    for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py']:cf.run('new_'+n[:-3],['python',str(analysis/n)],analysis)
    cf.save('canonical_equivalence_after_remap.json',proof(analysis,baseline))
    latest=json.loads((analysis/'exact_complement.json').read_bytes());assert not latest['errors']
    for a,b in zip(latest['cameras'],previous['cameras']):assert sorted(a['bundle_pairs'])==sorted(b['bundle_pairs']) and sorted(a['complement_launch_pins'])==sorted(b['complement_launch_pins']) and a['complement_launch_pins']
    check();cf.save('new_syn_validated.json',{'sha256':h,'canonical_pairs':1280,'physical_pairs':1320,'complements':[len(c['complement_launch_pins']) for c in latest['cameras']]})
    marks=cf.run('pnr',cmd('pnr'),HERE);route=HERE/'place_route/v7_sdt_top_pnr.adf'
    assert route.exists() and route.stat().st_size and 'Process "Place & Route" started.' in marks and 'Process "Place & Route" done.' in marks
    cf.save('pnr_artifact.json',{'path':str(route),'sha256':sha(route)});check()
    result=subprocess.run([__import__('sys').executable,'-u',str(Path(__file__).with_name('audit_fixed.py')),'physical_exact_09','standard_flow_exact09.pds'])
    assert result.returncode==0,'Acceptance gates open; no bit'
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
