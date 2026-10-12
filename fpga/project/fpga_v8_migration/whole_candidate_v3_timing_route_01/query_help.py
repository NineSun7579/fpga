from build_candidate import *
idle('before_pnr_help')
verify_protected()
work=HERE/'pnr_help'; work.mkdir()
command=[str(PDS),'-file',str(HERE/'query_pnr_help.tcl'),'-work_dir',str(work),'-project_name','timing_route_pnr_help']
save('pnr_help_started.json',{'command':command})
with (HERE/'pnr_help.log').open('xb') as log:
    result=subprocess.run(command,cwd=work,stdout=log,stderr=subprocess.STDOUT)
save('pnr_help_result.json',{'exit_code':result.returncode,'command':command})
verify_protected()
print((HERE/'pnr_help.log').read_text(errors='replace'))
