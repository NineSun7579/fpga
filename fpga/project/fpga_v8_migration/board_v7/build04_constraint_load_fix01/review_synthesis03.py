"""Record all 1284 native relationships and their actual budget annotation status."""
import sys,json,re
sys.dont_write_bytecode=True
import runner as r
r.E=r.E/'rebuild03';r.W=r.E/'candidate02'
from native_audit import pairs,cdb
from binding_review import sexpr,fields
raw=cdb('synthesis_native');root=sexpr(raw)
mm={fields(n)['CDBID'][0]:fields(n) for n in root[1:] if isinstance(n,list) and n and n[0]=='MMD' and fields(n).get('DELAY')==['15238']}
assert len(mm)==4 and all(v.get('DATAPATH_ONLY')==['1'] for v in mm.values())
assert not re.search(rb'\(CLKGP\b',raw)
gf=r.E/'synthesis_native/analysis/graph.json';g=json.loads(gf.read_bytes());pp=pairs(g,1284)
rows=[];bound=[];residual=[]
for p in pp:
 def ids(pin,typ):
  cell,port=pin.rsplit('/',1)
  return {f['CDBID'][0] for n in g['primitives'][cell]['cdb_entries'] for f in [fields(n)] if f.get('PINNAME')==[port] and f.get('TYPE')==[typ] and f.get('CDBID',[''])[0] in mm}
 shared=ids(p['launch_CLK'],'1')&ids(p['capture_D'],'3')
 row={**p,'native_budget_CDBIDs':sorted(shared)};rows.append(row)
 bit=int(re.search(r'/host_bank\[(\d+)\]',p['capture_D'])[1])
 if bit<480:
  assert len(shared)==1;bound.append(row)
 else:
  assert not shared;residual.append(row)
assert len(bound)==1280 and len(residual)==4
assert all(len({x['native_budget_CDBIDs'][0] for x in bound if x['camera']==cam})==1 for cam in range(4))
src=json.loads((r.E/'sourcehash.json').read_bytes());assert all(r.sha(r.W/n)==h for n,h in src['hashes'].items())
r.save('synthesis03_full_actual_binding_review.json',{'actual_total_pairs':1284,'native_15238_bound_pairs':1280,'residual_unannotated_signature_pairs':residual,'rows':rows,'four_budget_records':mm,'no_old_CLKGP':True,'source741_byte_equal':True,'graph_sha256':r.sha(gf),'CDB_sha256':r.sha(r.E/'synthesis_native_CDB_raw.txt'),'MAP_count_required':1280,'PNR_not_qualified_by_this_review':True})
r.guard()
print('Actual synthesis03: 1280 native budget-bound dynamic pairs + 4 unannotated signature pairs; MAP count remains unresolved')
