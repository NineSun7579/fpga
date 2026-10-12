"""Execute registered map/PNR actions using recovered actual DB, not RTL precheck."""
from prepare_route import *
def main():
    idle('registered_physical')
    out=HERE/'physical_registered_01';out.mkdir()
    project=(HERE/'route01_physical.pds').read_bytes()
    recovered=HERE/'physical_03/route01_recovered_syn.adf';assert recovered.exists()
    # A DB-only project has no RTL compilation dependencies. Set the actual top
    # and explicit recovered synthesis input on the registered mapping action.
    project=re.sub(rb'\(_option input_db_file\s+\(_file "physical_0[34]/route01_recovered_syn.adf"',b'(_option input_db_file\n                (_file "'+recovered.as_posix().encode()+b'"',project)
    if b'(_option top_module' not in project:
        project=project.replace(b'(_command cmd_devmap',b'(_command cmd_devmap\n            (_option top_module (_string "v7_sdt_top"))')
    target=HERE/'registered_physical.pds';target.write_bytes(project)
    stages=[]
    for stage in ['devmap','pnr']:
        idle('registered_'+stage)
        cmd=[str(PDS),'-project',str(target),'-run',stage,'-work_dir',str(HERE)]
        with (out/(stage+'_shell.log')).open('xb') as log:
            p=subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
        artifact=HERE/('device_map/v7_sdt_top_map.adf' if stage=='devmap' else 'place_route/v7_sdt_top_pnr.adf')
        stages.append({'stage':stage,'exit_code':p.returncode,'artifact_exists':artifact.exists()});save('physical_registered_01/result.json',stages)
        assert p.returncode==0 and artifact.exists(),stage
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    assert all(sha(Path(p))==v for p,v in guard.items())
    save('pnr_result.json',{'exit_code':0,'actual_pnr_completed':True,'inputs_and_build01_unchanged':True,'timing_verified':False,'route_sha256':sha(HERE/'place_route/v7_sdt_top_pnr.adf')})
if __name__=='__main__':main()
