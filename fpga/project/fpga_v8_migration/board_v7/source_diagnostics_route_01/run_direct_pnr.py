from prepare_route import *
def main():
    idle('direct_pnr')
    out=HERE/'direct_pnr_01';out.mkdir()
    project=(HERE/'registered_physical.pds').read_bytes()
    recovered=HERE/'physical_03/route01_recovered_syn.adf'
    project=project.replace(b'device_map/v7_sdt_top_map.adf',recovered.as_posix().encode())
    target=HERE/'direct_pnr.pds';target.write_bytes(project)
    cmd=[str(PDS),'-project',str(target),'-run','pnr','-work_dir',str(HERE)]
    print('START PNR WITH ACTUAL SYNTHESIS DB',flush=True)
    with (out/'shell.log').open('xb') as log:p=subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
    routes=list((HERE/'place_route').glob('*_pnr.adf'))
    save('direct_pnr_01/result.json',{'exit_code':p.returncode,'routes':[str(x) for x in routes]})
    assert p.returncode==0 and routes
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    assert all(sha(Path(p))==v for p,v in guard.items())
    save('pnr_result.json',{'exit_code':0,'actual_pnr_completed':True,'inputs_and_build01_unchanged':True,'timing_verified':False,'routes':[str(x) for x in routes]})
if __name__=='__main__':main()
