"""Audit existing actual exports only, no PDS rerun or failed artifact overwrite."""
from controller04 import *
import controller04
original_save=save
def audit_save(name,value):
    if (E/name).exists():
        revision=next((x[2:] for x in sys.argv if x.startswith('--audit_revision')), 'audit_revision02')
        name=Path(name).stem+'_'+revision+Path(name).suffix
    original_save(name,value)
controller04.save=audit_save
save=audit_save
try:
    verify()
    save('audit_resume_launch.json',{'pid':os.getpid(),'shell':sys.executable,'command':sys.argv,'manifest_sha256':sha(HERE/'manifest.json'),'parser_and_adapter_sha256':{str(p):sha(p) for p in (RUNTIME/'analysis_tools').glob('*.py')}})
    graphs={}
    for label,stage in [('compile','compile'),('actual','synthesis')]:
        gp=E/label/'analysis/graph.json';dump=E/label/'synthesis_export/synthesis_dump.txt'
        rec=load(E/(label+'_graph_artifact.json'))
        adf=HERE/('compile/v7_sdt_top_comp.adf' if label=='compile' else 'synthesize/v7_sdt_top_syn.adf')
        require(sha(gp)==rec['graph_sha256'] and sha(dump)==rec['dump_sha256'] and sha(adf)==rec['source_adf_sha256'],'Actual graph/artifact binding changed')
        graphs[stage]=endpoint_audit(stage,load(gp))
    verify()
    require(not any((HERE/d).exists() for d in ['device_map','place_route','generate_bitstream']),'Unauthorized stage output')
    files=[HERE/'compile/v7_sdt_top_comp.adf',HERE/'synthesize/v7_sdt_top_syn.adf',HERE/'compile/cmr.db',HERE/'synthesize/snr.db',E/'compile/analysis/graph.json',E/'actual/analysis/graph.json']
    binding={str(p):sha(p) for p in files};save('final_artifact_binding.json',binding)
    save('actual_result.json',{'status':'PASS_COMPILE_SYNTHESIS_EXPORT_INDEPENDENT60_ONLY','root':str(HERE),'top':'v7_sdt_top','stages':{s:{'status':p['status'],'independent_registers':p['independent_registers'],'independent_sync':p['independent_sync'],'independent_reset':p['independent_reset'],'failed_checks':len(p['failed_checks'])} for s,p in graphs.items()},'final_artifacts':binding,'manifest_sha256':sha(HERE/'manifest.json'),'build03_full_hashes_unchanged':True,'sources741_byte_identical_build03':True,'mapping_started':False,'pnr_started':False,'bit_generated':False,'remote_or_device_operations':False,'constraints_qualified':False,'next_gate':'Main-session complete60 placement constraints required; no automatic mapping/route admission','failures_preserved':[str(p) for p in E.glob('failure_*.txt')]})
    print('真实compile/synthesis与两个实际图：独立60端点审计全部PASS',flush=True)
except BaseException:
    p=E/('failure_'+str(time.time_ns())+'.txt');p.write_text(traceback.format_exc(),encoding='utf-8');print(str(p),flush=True);raise
