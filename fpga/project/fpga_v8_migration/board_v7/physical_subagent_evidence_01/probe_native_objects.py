"""Read-only DB export after failed FDC import, serial with the implementation."""
from continue_fixed import BASE,HERE,OUT,PDS,sha,busy
from pathlib import Path
import subprocess,time,json
while busy():time.sleep(10)
# Failed FDC import stops the implementation controller before any further PDS call.
attempt=OUT/'native_probe_07';attempt.mkdir(exist_ok=False)
hashes={}
for stage,name in [('compile','v7_sdt_top_comp.adf'),('synthesize','v7_sdt_top_syn.adf')]:
    db=HERE/stage/name
    assert db.exists()
    hashes[str(db)]=sha(db)
    script=attempt/(stage+'.tcl')
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+db.as_posix()+'} -output {'+(attempt/(stage+'_dump.txt')).as_posix()+'}\nhelp dev_map\nhelp synthesize\n',encoding='ascii')
    assert not busy()
    with (attempt/(stage+'.log')).open('xb') as log:
        p=subprocess.run([str(PDS),'-file',str(script),'-work_dir',str(attempt),'-project_name','native_probe07_'+stage],cwd=attempt,stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0 and sha(db)==hashes[str(db)]
(attempt/'input_hashes.json').write_text(json.dumps(hashes,indent=2))
print('Read-only compile/synthesis object exports ready',flush=True)
