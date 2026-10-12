from build_candidate import *
import xml.etree.ElementTree as ET
out=HERE/'evidence_02';out.mkdir(exist_ok=True)
db=HERE/'synthesize/snr.db'
tables={}
for _,el in ET.iterparse(db,events=['end']):
    if el.tag=='table' and el.attrib.get('id') in ['no_clock_detailed_report','loops_detailed_report','latch loops_detailed_report','latchs_detailed_report','synthesize_check_timing_summary','synthesize_report_clock_interaction','synthesize_report_timing_clock_summary']:
        tables[el.attrib['id']]=ET.tostring(el,encoding='unicode')
vm=(HERE/'synthesize/fpga_v8_cooperative_top_v2_rfg01_syn.vm').read_bytes()
guard=next(m[0] for m in re.finditer(rb'\bmodule\s+(\w+).*?\bendmodule\b',vm,re.S) if m[1].startswith(b'fpga_v8_reset_fault_guard'))
cells=[]
for m in re.finditer(rb'(?m)^\s*(GTP_\w+)\b.*?;',guard,re.S):
    if any(k in m[0] for k in [b'fault',b'reconfiguration_required',b'N165',b'qualified']):
        cells.append(m[0].decode('ascii','backslashreplace'))
lines=[]
for name in ['synthesize/run.log','place_route/run.log','pnr_shell.log']:
    data=(HERE/name).read_bytes()
    for i,x in enumerate(data.splitlines(),1):
        if any(k in x for k in [b'STA-3001',b'STA-3011',b'dual asynchronous',b'u_reset_fault_guard/qualified',b'u_reset_fault_guard/N165',b'bad_event']):
            lines.append({'file':name,'line':i,'text':x.decode('ascii','backslashreplace')})
save('evidence_02/guard_mapping_blocker.json',{'status':'IMPLEMENTATION_SIGNOFF_BLOCKED','source_unchanged':True,
    'synthesis_db_sha256':sha(db),'exact_check_tables':tables,'mapped_cells':cells,'log_evidence':lines,
    'findings':['Two mapped guard GTP_DLATCH_C: fault_cp and reconfiguration_required_cp',
                'No clock on both latch G pins; bad_event and N165 nodes also lack associated clocks',
                'N165/reconfiguration_required_cp/qualified feedback forms a size-7 combinational loop; STA automatically breaks timing arcs',
                'qualified[5] optimized as constant zero; mapped semantics must be reviewed, not assumed equivalent'],
    'next_required_fix':'New separate candidate must re-express asynchronous fault capture and sticky reconfiguration with supported PANGO sequential primitives, eliminate control-clock latch feedback, and preserve short-pulse fault capture/admission closure contract. Re-run behavioral/technology mapping checks and full routed all-corner STA without clock cuts.',
    'no_new_false_path':True,'timing_cuts_are_vendor_automatic_loop_breaks_not_authorized_agent_exceptions':True,
    'current_route_preserved':True,'board_ready':False})
verify_protected()
print('Concrete guard mapping blocker saved; mapped evidence cells',len(cells))
