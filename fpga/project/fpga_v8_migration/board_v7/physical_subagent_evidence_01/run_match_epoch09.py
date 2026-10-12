"""Preserved importer tests of exact stage-specific names; never accept synthesis."""
from pathlib import Path
import json, subprocess
from native_query08 import BASE, PDS, idle
from prepare_query_epoch08 import main as prepare

OUT=BASE/'fixed_06/match_epoch09'
def main():
    idle()
    query=BASE/'match_objects09.fdc'
    prepare(OUT,query)
    cmd=[PDS,'-project',str(OUT/'query_epoch08.pds'),'-run','synthesize','-work_dir',str(OUT)]
    (OUT/'launch.json').write_text(json.dumps({'command':cmd,'acceptance':False},indent=2))
    with (OUT/'shell.log').open('xb') as f:
        r=subprocess.run(cmd,cwd=OUT,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/'shell.log').read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    (OUT/'shell.txt').write_text(text,encoding='utf8')
    lines=[x for x in text.splitlines() if x.startswith('E:') or 'MATCH09' in x or x.startswith('Process')]
    (OUT/'result.json').write_text(json.dumps({'exit':r.returncode,'findings':lines,'acceptance':False},indent=2))
    print('\n'.join(lines),flush=True)
if __name__=='__main__':main()
