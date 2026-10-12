"""Preserve complete native evidence of candidate02 pair/site gate failure."""
import json,tkinter,re
import runner as r
from native_audit import pairs
gfile=r.E/'mapping_native/analysis/graph.json';g=json.loads(gfile.read_bytes())
rows=pairs(g,1320)
t=tkinter.Tcl();draft=r.W/'constraints_live/production60.lcf';pcf=r.W/'device_map/v7_sdt_top.pcf'
targets=[t.splitlist(l) for l in draft.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
places=[t.splitlist(l) for l in pcf.read_text().splitlines() if l.startswith('def_inst_site ')]
site_rows=[]
for cmd in targets:
 s=cmd[1][2:];cells=[c for c in g['primitives'] if c==s or c.startswith(s+'/')]
 detail=[]
 for c in cells:
  v=g['primitives'][c];locations=[p for p in places if p[1].lstrip('\\')==c]
  detail.append({'cell':c,'type':v['type'],'parameters':v['parameters'],'default_parameters':v['default_parameters'],'ports':v['ports'],'PCF':locations,'native_sites_match':len(locations)==1 and locations[0][2]==cmd[3],'exact_gopQ':v['type']=='gopQ'})
 site_rows.append({'source':s,'required_site':cmd[3],'mapped':detail})
source=json.loads((r.E/'sourcehash.json').read_bytes());assert all(r.sha(r.W/n)==h for n,h in source['hashes'].items())
r.save('candidate02_actual_failed_gate_review.json',{'status':'FAIL_NATIVE_PAIR_COUNT_AND_EXACT_STORAGE_GATE','map_tool_rc':json.loads((r.E/'mapping02_receipt.json').read_bytes())['rc'],'actual_pairs':1320,'required_pairs':1280,'signature_constant_pairs':40,'sites':site_rows,'graph_sha256':r.sha(gfile),'PCF_sha256':r.sha(pcf),'source741_byte_equal':True,'PNR_started':False,'bit':False,'no_gates_relaxed':True})
r.guard()
print('candidate02 actual FAIL preserved: 1320/1280 pairs; 60 sourcepaths native types recorded; source741 equal; frozen drift=0')
