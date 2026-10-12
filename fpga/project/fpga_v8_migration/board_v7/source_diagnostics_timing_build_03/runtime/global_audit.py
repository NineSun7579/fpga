"""Fresh build03 global ten-group STA/IO112/HSST/motion32 audit; no bit stage."""
from pathlib import Path
import sys
from preflight import HERE, DATA, load, sha, require
from physical_flow import EVIDENCE, PDS, run, record, protected, snapshot
sys.path.insert(0,str(Path(__file__).resolve().parent/'libraries'))

def audit(route):
    protected();receipt=load(EVIDENCE/'pnr_artifact.json')
    require(sha(route)==receipt['sha256'],'Global audit route not actual PNR artifact')
    export=EVIDENCE/'final_export';export.mkdir()
    script=export/'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        '.switch_db -input {'+route.as_posix()+'} -output {'+(export/'routed_dump.txt').as_posix()+'}\n'
        'report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE\n',encoding='ascii')
    before=sha(route);inputs=snapshot()
    run('final_export',[str(PDS),'-file',str(script),'-work_dir',str(export),'-project_name','build03_global_routed'],export)
    protected();require(sha(route)==before and snapshot()==inputs,'Global report changed route/inputs')
    record('final_export_result.json',{'exit_code':0,'route_db_unchanged':True,'protected_unchanged':True,'route_sha256_after':before,
           'launch_sha256':sha(EVIDENCE/'final_export_launch.json'),'log_sha256':sha(EVIDENCE/'final_export.log')})
    # Inputs_before for final review means the exact derived constraints entering
    # PNR. The original logical constraints remain in the frozen741 source set.
    record('inputs_before.json',inputs)
    from summarize_route import extract
    import raw_audit
    record('raw_gate_reuse.json',{'source':str(Path(raw_audit.__file__)),'source_sha256':sha(raw_audit.__file__),
           'executed_sha256':sha(raw_audit.__file__),'scope':'local parser and real new routed dump/report only'})
    raw_audit.main()
    (EVIDENCE/'evidence').mkdir(exist_ok=True)
    stages={s:extract(HERE/s/db,s) for s,db in [('synthesize','snr.db'),('place_route','prr.db')]}
    record('evidence/stage_tables.json',stages)
    pins=stages['place_route']['pnr_io_report']['rows'];old=load(DATA/'reference_tables.json')['place_route']['pnr_io_report']['rows']
    record('evidence/io_audit.json',{'passed':len(pins)==112 and pins==old,'pins':len(pins),'matches_frozen_v7':pins==old})
    require(len(pins)==112 and pins==old,'PCB IO112/electrical identity drift')
    record('audit_parser_binding.json',{'source':str(Path(__file__)),'source_sha256':sha(__file__),
           'executed_sha256':sha(__file__),'bit_stage_removed':True,'old_graph_fallback_removed':True,
           'stream_parser_sha256':sha(HERE/'runtime/targeted_reports.py'),'runtime_root':str(HERE)})
