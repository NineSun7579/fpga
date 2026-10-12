"""Compare raw ADIF leaf type and complete port names against every graph cell."""
from pathlib import Path
import hashlib,importlib.util,json,sys
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent;B=P.parent;R=B/'build04_mailbox_clock_review01';sys.path.insert(0,str(R))
spec=importlib.util.spec_from_file_location('independent_byte_reader',R/'independent_adif_check.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
results=[]
for name,root in [('compile',B/'source_diagnostics_timing_build_04/evidence/runtime/compile'),('synthesis',B/'source_diagnostics_timing_build_04/evidence/runtime/actual'),('mapped',B/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping'),('build01',B/'source_diagnostics_timing_build_01/evidence/actual')]:
 dump=root/'synthesis_export/synthesis_dump.txt';gp=root/'analysis/graph.json';cells=reader.read_cells(dump.read_bytes());g=json.loads(gp.read_bytes());leaves={}
 def walk(key,path):
  ports,insts,nets=cells[key]
  for inst,typ,view in insts:
   child=path+'/'+inst if path else inst
   if cells[(typ,view)][1]:walk((typ,view),child)
   else:
    assert child not in leaves;leaves[child]=(typ,cells[(typ,view)][0])
 top=[k for k in cells if k[0]=='v7_sdt_top'];assert len(top)==1;walk(top[0],'')
 assert set(leaves)==set(g['primitives'])
 for cell,(typ,ports) in leaves.items():assert typ==g['primitives'][cell]['type'] and set(ports)==set(g['primitives'][cell]['ports']),cell
 results.append({'stage':name,'dump_sha256':sha(dump),'graph_sha256':sha(gp),'all_leaf_types_and_full_port_names_checked':len(leaves),'status':'PASS_RAW_ADIF_TYPES_PORT_NAMES'})
 print(name,len(leaves),'raw leaf types and full port names verified',flush=True)
 del cells,g,leaves
(P/'independent_raw_type_schema_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
