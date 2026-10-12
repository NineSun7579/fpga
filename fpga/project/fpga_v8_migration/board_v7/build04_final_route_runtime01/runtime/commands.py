"""Official Tcl command preparation only. All generated Tcl starts locked."""
from contract import HERE,sha
from pathlib import Path
import json
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
LOCK='error {BLOCKED: main-session bound enable and real evidence required; timing CDB reload remains separately unproven}\n'
def generate(pairs,classified):
    dest=HERE/'commands';dest.mkdir(exist_ok=True);root=HERE/'execution01'
    route=(root/'place_route/v7_sdt_top_pnr.adf').as_posix()
    scripts={}
    scripts['pnr_reload.tcl']=ARCH+''.join('add_constraint {'+(root/'constraints'/n).as_posix()+'}\n' for n in ['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc'])+'add_constraint {'+(root/'inputs/device_map/v7_sdt_top.pcf').as_posix()+'}\npnr -force_to_run -input_db_file {'+(root/'inputs/device_map/v7_sdt_top_map.adf').as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation\n'
    scripts['global10.tcl']=ARCH+'.switch_db -input {'+route+'} -output {'+(root/'reports/routed_dump.txt').as_posix()+'}\nreport_timing -input_db_file {'+route+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE\n'
    def query(name,pairs=(),ends=()):
        def listing(xs):return '{'+' '.join('{'+p+'}' for p in sorted(set(xs)))+'}'
        cmd=ARCH+'report_timing -input_db_file {'+route+'} -force_to_run -delay_type min_max -report_exception TRUE -input_pins TRUE -nworst 2 -max_path 1024'
        if pairs:cmd+=' -from '+listing(a for a,b in pairs);ends=[b for a,b in pairs]
        scripts[name]=cmd+' -to '+listing(ends)+'\n'
    physical=[(p['CLK'],p['D']) for p in pairs]
    query('single_pair.tcl',pairs=physical[:1])
    for i in range(0,len(physical),64):query('mailbox_batch_%03d.tcl'%(i//64),pairs=physical[i:i+64])
    query('reset32.tcl',ends=[r['reset'] for r in classified['rows'] if r['chain'] in ['cr','hr','reset_pipe']])
    query('reset32_MPW.tcl',ends=[r['CLK'] for r in classified['rows'] if r['chain'] in ['cr','hr','reset_pipe']])
    query('sync_later16.tcl',pairs=[(r['launch_CLK'],r['capture_D']) for r in classified['ordinary_pairs']])
    # These synthesis endpoint scripts are templates: regenerate from independently
    # verified routed graph before reporting; never silently inherit physical names.
    scripts['bit_EXPLICIT_DB_LOCKED.tcl']=ARCH+'gen_bit_stream -input_db_file {'+route+'} -force_to_run -create_bit_file TRUE\n'
    for name,raw in scripts.items():(dest/name).write_text(LOCK+raw,encoding='ascii')
    manifest={'commands':{n:{'sha256':sha(dest/n),'argv':['C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe','-file',str(dest/n),'-work_dir',str(root if n=='pnr_reload.tcl' else root/'reports'/Path(n).stem),'-project_name','v7_sdt_top']} for n in scripts},'all_scripts_locked':True,'target_endpoint_revision':'synthesis templates; routed independent rebinding required','mailbox_batches':20}
    (HERE/'official_commands.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='ascii')
