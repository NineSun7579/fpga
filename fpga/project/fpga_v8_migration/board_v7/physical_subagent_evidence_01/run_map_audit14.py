"""Audit explicit-input mapping before any routed implementation."""
from pathlib import Path
import json,subprocess,shutil,hashlib,traceback
from native_query08 import BASE,PDS,idle
ROOT=BASE/'fixed_06'; MAP=ROOT/'stage_map13'; OUT=ROOT/'map_audit14'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label,cmd,cwd):
    idle()
    (OUT/(label+'_launch.json')).write_text(json.dumps({'command':cmd},indent=2))
    with (OUT/(label+'.log')).open('xb') as f:r=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/(label+'.log')).read_bytes();text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    errors=[x for x in text.splitlines() if x.startswith('E:') or 'Timing-4003' in x]
    (OUT/(label+'_result.json')).write_text(json.dumps({'exit_code':r.returncode,'errors':errors},indent=2))
    assert r.returncode==0 and not errors,(label,errors)
    print(label,'DONE',flush=True)
def main():
    idle();OUT.mkdir(exist_ok=False)
    receipt=json.loads((MAP/'result.json').read_bytes());assert not receipt['errors']
    source=MAP/'device_map/v7_sdt_top_map.adf'
    assert sha(source)==next(iter(receipt['mapped_artifacts'].values()))
    db=OUT/'mapped_input.adf';shutil.copy2(source,db);h=sha(db)
    actual=OUT/'actual';(actual/'analysis').mkdir(parents=True);(actual/'synthesis_export').mkdir()
    script=OUT/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+(actual/'synthesis_export/synthesis_dump.txt').as_posix()+'}\n',encoding='ascii')
    run('export_map',[PDS,'-file',str(script),'-work_dir',str(actual),'-project_name','map_audit14'],actual)
    origin=ROOT/'synthesis_epoch10/actual/analysis'
    for n in ['parse_objects.py','resolve_manifest.py','derive_exact_complement.py','classify_paths.py','B_one_pair.sdc']:shutil.copy2(origin/n,actual/'analysis'/n)
    for n in ['parse_objects','resolve_manifest','derive_exact_complement','classify_paths']:
        run(n,['python',str(actual/'analysis'/(n+'.py'))],actual)
    m=json.loads((actual/'analysis/manifest.json').read_bytes());e=json.loads((actual/'analysis/exact_complement.json').read_bytes())
    old=json.loads((origin/'exact_complement.json').read_bytes())
    assert not m['errors'] and not e['errors']
    for a,b in zip(e['cameras'],old['cameras']):
        assert a['bundle_pairs']==b['bundle_pairs'] and a['complement_launch_pins']==b['complement_launch_pins']
    (OUT/'topology.json').write_text(json.dumps({'pairs':1280,'complements':[len(c['complement_launch_pins']) for c in e['cameras']],'mapped_db_sha256':h,'provenance':m['clock_provenance'],'bit_permitted':False},indent=2))
    timing=OUT/'timing';timing.mkdir()
    t=timing/'report.tcl'
    t.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nreport_timing -input_db_file {'+db.as_posix()+'} -force_to_run -delay_type min_max -nworst 2 -max_path 10000 -input_pins TRUE -report_exception TRUE -from {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk} -to {ddrphy_sysclk}\n',encoding='ascii')
    run('report_mailbox',[PDS,'-file',str(t),'-work_dir',str(timing),'-project_name','map_audit14_timing'],timing)
    assert sha(db)==h and sha(source)==h
    reports={str(p.relative_to(timing)):sha(p) for p in timing.rglob('*.rtr')}
    (OUT/'report_identity.json').write_text(json.dumps({'reports':reports,'input_unchanged':True,'path_coverage_pending':True,'pnr_permitted':False},indent=2))
    assert reports,'No actual report'
    print('Mapped graph 1280 pairs validated; actual report ready for coverage audit',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
