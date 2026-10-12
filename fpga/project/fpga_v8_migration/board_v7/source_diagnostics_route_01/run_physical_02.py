from prepare_route import *
import sys
def main():
    idle('physical_02')
    attempt=sys.argv[1] if len(sys.argv)>1 else 'physical_02'
    out=HERE/attempt;out.mkdir()
    script=out/'run.tcl'
    recovered=out/'route01_recovered_syn.adf'
    constraints=''.join('add_constraint {'+(HERE/'physical_constraints'/n).as_posix()+'}\n' for n in ['sfp.fdc','cdc.fdc','clock.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc'])
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+constraints+
        '.switch_db -input {'+(HERE/'synthesis_export/synthesis_dump.txt').as_posix()+'} -output {'+recovered.as_posix()+'}\n'
        'dev_map -force_to_run -top_module v7_sdt_top -input_db_file {'+recovered.as_posix()+'}\n'
        'pnr -force_to_run -input_db_file {'+(HERE/'device_map/v7_sdt_top_map.adf').as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation\n',encoding='ascii')
    cmd=[str(PDS),'-file',str(script),'-work_dir',str(HERE),'-project_name','route01_physical']
    save(attempt+'/launch.json',{'command':cmd,'original_real_synthesis_dump':str(HERE/'synthesis_export/synthesis_dump.txt'),'dump_sha256':sha(HERE/'synthesis_export/synthesis_dump.txt')})
    print('START DIRECT ACTUAL DB PHYSICAL FLOW',flush=True)
    with (out/'shell.log').open('xb') as log:result=subprocess.run(cmd,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
    route=HERE/'place_route/v7_sdt_top_pnr.adf'
    save(attempt+'/result.json',{'exit_code':result.returncode,'routed_db_exists':route.exists()})
    assert result.returncode==0 and route.exists()
    print('ACTUAL PNR DB EXISTS',flush=True)
if __name__=='__main__':main()
