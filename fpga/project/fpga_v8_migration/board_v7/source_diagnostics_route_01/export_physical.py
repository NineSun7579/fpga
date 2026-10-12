"""Routed full ten-group report, actual physical DB and report API evidence."""
from prepare_route import *
def main():
    idle('physical_export')
    receipt=json.loads((HERE/'pnr_result.json').read_bytes())
    assert receipt['exit_code']==0 and receipt['inputs_and_build01_unchanged']
    out=HERE/'final_export';out.mkdir()
    route=HERE/'place_route/v7_sdt_top_pnr.adf';h=sha(route)
    script=HERE/'final_export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        '.switch_db -input {'+route.as_posix()+'} -output {'+(out/'routed_dump.txt').as_posix()+'}\n'
        'report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception TRUE\n'
        'help report_timing\n',encoding='ascii')
    with (HERE/'final_export_shell.log').open('xb') as log:
        p=subprocess.run([str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','route01_routed_evidence'],cwd=out,stdout=log,stderr=subprocess.STDOUT)
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    save('final_export_result.json',{'exit_code':p.returncode,'route_sha256_before':h,'route_sha256_after':sha(route),'route_db_unchanged':sha(route)==h,'protected_unchanged':all(sha(Path(p))==v for p,v in guard.items())})
    assert p.returncode==0 and sha(route)==h
    print('Full physical export complete',flush=True)
if __name__=='__main__':main()
