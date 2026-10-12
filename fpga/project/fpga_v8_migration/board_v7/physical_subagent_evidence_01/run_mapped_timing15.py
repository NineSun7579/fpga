from pathlib import Path
import json,subprocess,hashlib,traceback
from native_query08 import BASE,PDS,idle
OUT=BASE/'fixed_06/mapped_timing15'
SOURCE=BASE/'fixed_06/map_audit14'
def main():
    idle();OUT.mkdir(exist_ok=False)
    manifest=json.loads((SOURCE/'mapped_channel_manifest.json').read_bytes());assert manifest['pair_count']==1280
    db=SOURCE/'mapped_input.adf';h=hashlib.sha256(db.read_bytes()).hexdigest()
    starts=sorted({a for a,b in manifest['pairs']});ends=sorted({b for a,b in manifest['pairs']})
    def collection(items):return '{'+' '.join('{'+x+'}' for x in items)+'}'
    script=OUT/'report.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nreport_timing -input_db_file {'+db.as_posix()+'} -force_to_run -delay_type min_max -nworst 2 -max_path 10000 -input_pins TRUE -report_exception TRUE -from '+collection(starts)+' -to '+collection(ends)+'\n',encoding='ascii')
    cmd=[PDS,'-file',str(script),'-work_dir',str(OUT),'-project_name','mapped_timing15']
    (OUT/'launch.json').write_text(json.dumps({'command':cmd,'db_sha256':h,'expected_pairs':manifest['pairs'],'bit_permitted':False},indent=2))
    with (OUT/'shell.log').open('xb') as f:r=subprocess.run(cmd,cwd=OUT,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/'shell.log').read_bytes();text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    errors=[x for x in text.splitlines() if x.startswith('E:') or 'Timing-4003' in x]
    (OUT/'shell.txt').write_text(text,encoding='utf8')
    (OUT/'result.json').write_text(json.dumps({'exit_code':r.returncode,'errors':errors,'db_unchanged':hashlib.sha256(db.read_bytes()).hexdigest()==h,'reports':[str(p) for p in OUT.rglob('*.rtr')],'coverage_pending':True,'bit_permitted':False},indent=2))
    print(text[-9000:],flush=True);assert r.returncode==0 and not errors
if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        raise
