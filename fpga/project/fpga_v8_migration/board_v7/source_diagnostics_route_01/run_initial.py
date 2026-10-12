from prepare_route import *
def main():
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    stages=[]
    for stage in ['compile','synthesize']:
        idle(stage);assert all(sha(Path(p))==h for p,h in guard.items())
        cmd=[str(PDS),'-project',str(HERE/'project.pds'),'-run',stage,'-work_dir',str(HERE)]
        print('START',stage,cmd,flush=True)
        with (HERE/(stage+'_shell.log')).open('xb') as log:r=subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
        stages.append({'stage':stage,'exit':r.returncode});save('initial_result.json',stages)
        assert r.returncode==0,stage
        print('DONE',stage,flush=True)
    idle('export')
    out=HERE/'synthesis_export';out.mkdir()
    script=HERE/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'+(HERE/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -output {'+(out/'synthesis_dump.txt').as_posix()+'}\n',encoding='ascii')
    with (HERE/'export_shell.log').open('xb') as log:r=subprocess.run([str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','route01_evidence'],cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0
    for n in ['parse_objects.py','resolve_manifest.py','classify_paths.py','derive_sta_sdc.py','derive_exact_complement.py']:
        r=subprocess.run(['C:/Users/NineSun/anaconda3/python.exe',str(HERE/'actual'/n)],cwd=HERE)
        assert r.returncode==0,n
    assert all(sha(Path(p))==h for p,h in guard.items())
    print('INITIAL SYNTHESIS AND ACTUAL MAPPING COMPLETE',flush=True)
if __name__=='__main__':main()
