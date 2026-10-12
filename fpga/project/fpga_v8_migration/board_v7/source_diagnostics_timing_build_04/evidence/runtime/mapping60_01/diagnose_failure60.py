"""Inventory only from this failed attempt; does not waive primitive semantics."""
from pathlib import Path
import json,hashlib,sys,tkinter,collections
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;B=E.parents[2]
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
from endpoint_detail import parameters
from graph_adapter import Resolver
def load(n):return json.loads((E/n).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,o):
    p=E/n;assert not p.exists();p.write_text(json.dumps(o,indent=2)+'\n',encoding='ascii')
gfile=E/'mapping/analysis/graph.json';g=load('mapping/analysis/graph.json');binding=load('graph_binding.json')
assert sha(gfile)==binding['graph_sha256']
pcf=E/'isolated_mapping_work/device_map/v7_sdt_top.pcf';assert sha(pcf)==binding['pcf_sha256']
tcl=tkinter.Tcl();commands=[]
for line in pcf.read_text(encoding='ascii').splitlines():
    if not line.strip() or line.lstrip().startswith('#'):continue
    parts=tcl.splitlist(line)
    if parts[0]=='def_inst_site':
        assert len(parts) in {3,4};commands.append({'cell':parts[1].lstrip('\\'),'site':parts[2],'impl':parts[3] if len(parts)==4 else None,'line':line})
def locations(rec):
    out=[]
    def walk(v):
        if not isinstance(v,list):return
        if len(v)==3 and v[:2]==['ATTRIBUTE','PAP_LOC']:out.append({'value':v[2][1].strip('"'),'entry':v})
        for x in v:walk(x)
    walk(rec.get('attributes',[]));walk(rec.get('cdb_entries',[]));return out
rows=[]
for t in load('fresh60_binding.json')['rows']:
    target=t['target'];sr=t['synthesis_row']
    cells=[c for c in g['primitives'] if c==target or c.rpartition('/')[0]==target]
    items=[]
    for cell in cells:
        rec=g['primitives'][cell];matched=[c for c in commands if c['cell']==cell];loc=locations(rec);occupants=[c for c in commands if c['site']==t['site']]
        outputs=[p for p,v in rec['ports'].items() if v['direction']=='OUTPUT' and cell+'/'+p in g['pin_net']]
        nets={p:g['pin_net'].get(cell+'/'+p) for p in rec['ports']}
        exact_q=cell+'/Q'
        actual_q=g['pin_net'].get(exact_q)
        driver_pins=Resolver(g).drivers(actual_q) if actual_q is not None else []
        items.append({'cell':cell,'type':rec['type'],'parameters':parameters(rec),'connected_outputs':outputs,'port_nets':nets,'exact_Q_pin_exists':actual_q is not None,'exact_Q_net_drivers':driver_pins,'pcf':matched,'PAP_LOC_CDB':loc,'site_occupants':occupants,'position_only_passed':bool(matched and loc) and {c['site'] for c in matched}=={t['site']} and {v['value'] for v in loc}=={t['site']} and {c['cell'] for c in occupants}=={cell},'accepted_by_this_attempt_storage_type_gate':rec['type']=='gopQ'})
    rows.append({'target':target,'site':t['site'],'camera':sr['camera'],'chain':sr['chain'],'bit':sr['bit'],'sync':sr['chain'] in {'ack_sync','req_sync','overrun_sync'},'actual_immediate_hierarchy_cells':items,'one_cell':len(items)==1})
types=collections.Counter(i['type'] for row in rows for i in row['actual_immediate_hierarchy_cells'])
counts={'targets':len(rows),'sync_targets':sum(r['sync'] for r in rows),'reset_targets':sum(not r['sync'] for r in rows),'one_actual_cell_targets':sum(r['one_cell'] for r in rows),'position_only_passed_targets':sum(r['one_cell'] and r['actual_immediate_hierarchy_cells'][0]['position_only_passed'] for r in rows),'exact_types':dict(types)}
save('failed_attempt_exact60_inventory.json',{'status':'DIAGNOSTIC_ONLY_PRODUCTION60_FAIL_RETAINED','counts':counts,'rows':rows,'graph_sha256':sha(gfile),'pcf_sha256':sha(pcf),'basis':'Exact target or exact immediate-parent path equality; Tcl exact actual-cell/site tokens; not substring','limitation':'Inventory and position-only results cannot prove full storage/clock/reset/INIT/CE/chain semantics; original endpoint failure retained'})
first=rows[0]
lines=['mapping60_01 失败诊断补充（未重跑工具）','','dev_map和.switch_db export真实exit0；工具receipt无被拒绝日志行，dmr无原生error。','实际fulltop graph已导出；独立60端点审计在camera0 cr[0]失败：Unique actual Q driver required ... set()。','',json.dumps(counts,ensure_ascii=False),'','这次图中实际类型按精确target层级逐项记录在failed_attempt_exact60_inventory.json；位置绑定只能作为位置诊断，不能替代被拒绝的完整端点语义证明。','生产60状态保持FAIL；不修改原parser/checker，不认未证实类型等价，不改源、不重跑、不PNR/bit/远程/program。']
p=E/'FAILURE_DIAGNOSIS_ZH.md';assert not p.exists();p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
save('failure_diagnosis_hashes.json',{n:sha(E/n) for n in ['failed_attempt_exact60_inventory.json','FAILURE_DIAGNOSIS_ZH.md','diagnose_failure60.py']})
print(json.dumps(counts));print('Production60 FAIL retained')
