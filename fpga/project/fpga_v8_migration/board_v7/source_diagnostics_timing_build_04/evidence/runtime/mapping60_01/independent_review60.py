"""Post-attempt strict review. No FPGA tool execution or graph substitution."""
from pathlib import Path
import json,hashlib,sys,tkinter,traceback,re
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;B=E.parents[2]
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
from endpoint_detail import parameters
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(x,m):
    if not x:raise RuntimeError(m)
def save(n,o):
    p=E/n;req(not p.exists(),'Review already exists');p.write_text(json.dumps(o,indent=2)+'\n',encoding='ascii')
def main():
    projects=[]
    for p in (E/'isolated_mapping_work').glob('*.pds'):
        text=p.read_bytes().decode('ascii')
        projects.append({'path':str(p),'sha256':sha(p),'copied_original':p.name=='project.pds','PDS_generated_work_project':p.name!='project.pds','metadata_fields':re.findall(r'\(_(?:comment|timespec|gci_state|db_output|output)\b[^\r\n]*',text),'registered_files':re.findall(r'\(_file "([^"]+)"',text),'bytes_ascii':text})
    save('PDS_work_project_metadata_receipt.json',{'projects':projects,'original_project_sha256':sha(B/'project.pds'),'all_work_project_hashes_recorded':True})
    result=load(E/'final_result.json');req(result['status']=='PASS_MAPPING_EXPORT_AUDIT60_ONLY','Attempt failed; production review BLOCKED')
    graph=E/'mapping/analysis/graph.json';g=load(graph);binding=load(E/'graph_binding.json');req(sha(graph)==binding['graph_sha256'],'Graph drift')
    mp=load(E/'mapping_endpoint_details.json');req(mp['status']=='PASS' and len(mp['rows'])==60 and len({r['cell'] for r in mp['rows']})==60,'Distinct60 proof')
    rows=[];sync=0
    for row in mp['rows']:
        rec=g['primitives'][row['cell']];p=parameters(rec);is_sync=row['chain'] in {'ack_sync','req_sync','overrun_sync'};sync+=is_sync
        expect={'IMPL_MODE':'Q','RS_MODE':'ASYNC','LRS_POL':'FALSE','LRS_EN':'TRUE','CLK_POL':'FALSE','GRS_EN':'TRUE','LATCH_EN':'FALSE','RSMUX_SEL':'LOCAL','FF_RS':'RESET' if is_sync else 'SET','FF_INIT':'0' if is_sync else '1'}
        checks={k:p.get(k)==v for k,v in expect.items()}
        checks['exact_gopQ']=rec['type']=='gopQ'
        checks['exact_storage_ports']=set(rec['ports'])=={'D','Q','CLK','RS','CE','CECO','RSCO'}
        checks['Q_not_combinational']=row['Q']==row['cell']+'/Q' and rec['ports']['Q']['direction']=='OUTPUT'
        checks['CE_disabled_or_local']=p.get('LCE_EN')=='FALSE' or (p.get('CEMUX_SEL')=='LOCAL' and p.get('LCE_POL')=='FALSE' and row['checks'].get('CE_constant_one_or_disabled')==True)
        checks['no_other_active_output']=all(row['cell']+'/'+pin not in g['pin_net'] for pin in ['CECO','RSCO'])
        checks['semantic_proof']=all(row['checks'].values())
        rows.append({'cell':row['cell'],'type':rec['type'],'expected_parameters':expect,'actual_parameters':p,'checks':checks,'passed':all(checks.values())})
    req(sync==28 and len(rows)-sync==32,'28sync/32reset count')
    loc=load(E/'native_pcf_exact60_audit.json');req(loc['passed'] and len(loc['rows'])==60,'Exact60 placement proof')
    tcl=tkinter.Tcl();pcf=E/'isolated_mapping_work/device_map/v7_sdt_top.pcf';cmds=[]
    for line in pcf.read_text(encoding='ascii').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        parts=tcl.splitlist(line)
        if parts[0]=='def_inst_site':cmds.append({'cell':parts[1].lstrip('\\'),'site':parts[2],'impl':parts[3] if len(parts)==4 else None})
    placements=[]
    for row in loc['rows']:
        occupants=[x for x in cmds if x['site']==row['site']]
        checks={'only_expected_cell_at_site':{x['cell'] for x in occupants}=={row['cell']},'no_impl_conflict':{x['impl'] for x in occupants}=={'impl_devCQ0'}}
        placements.append({'cell':row['cell'],'site':row['site'],'occupants':occupants,'checks':checks,'passed':all(checks.values())})
    clocks=load(E/'mapped_exact_clock_identity.json');req(clocks['passed'] and len(clocks['rows'])==60,'Exact clock identity proof missing')
    passed=all(r['passed'] for r in rows+placements)
    save('independent_review60.json',{'status':'PASS_PRODUCTION60_MAPPING_ONLY' if passed else 'FAIL','rows':rows,'placements':placements,'sync':sync,'reset':32,'graph_sha256':sha(graph),'pcf_sha256':sha(pcf),'producer_result_sha256':sha(E/'final_result.json'),'reviewer_sha256':sha(__file__),'next_gate':'Main review: full timing/IO/bit','pnr':False,'bit':False})
    req(passed,'Exact gopQ model/control/site conflict review failed')
if __name__=='__main__':
    try:main()
    except BaseException:
        if not (E/'independent_review60.json').exists():save('independent_review60.json',{'status':'FAIL','traceback':traceback.format_exc(),'no_tool_execution':True})
        print(traceback.format_exc());sys.exit(1)
