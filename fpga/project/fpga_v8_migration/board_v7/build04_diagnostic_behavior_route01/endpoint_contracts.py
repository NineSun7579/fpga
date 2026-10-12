import complete_binding as cb
from pathlib import Path
import sys,importlib.util,itertools,json
E=cb.E;B=cb.B
spec=importlib.util.spec_from_file_location('review_clock',E.parent/'build04_mapped_endpoint_review02/review.py');rv=importlib.util.module_from_spec(spec);spec.loader.exec_module(rv)
g=cb.load(E/'routed/analysis/graph.json');sg=cb.load(B/'evidence/runtime/actual/analysis/graph.json');mg=cb.load(B/'evidence/runtime/mapping60_01/mapping/analysis/graph.json');rv.SYN_GRAPH=sg
binding=cb.load(E/'official_model_binding60_refined.json');rows=binding['rows'];old=cb.load(E.parent/'build04_mapped_endpoint_review02/rows60.json')['rows'];cells=cb.load(E/'functional_instance_inventory.json')['cells'];nl=cb.Netlist(cells)
index={(x['camera'],x['chain'],x['bit']):(a,x) for a,x in zip(rows,old)};out=[]
for a,s in zip(rows,old):
 r={'logical':s['logical'],'routed_cell':a.get('routed_cell'),'checks':{},'errors':[]};out.append(r)
 try:
  c=a['routed_cell'];v=a['V_record'];root=s['clock_identity']['root_alias'];r['clock']=rv.clock_path(g,c+'/CLK',root);r['checks']['clock_identity']=True
 except Exception as ex:r['errors'].append('Clock '+str(ex));r['checks']['clock_identity']=False
 try:
  if s['bit']:
   prev,_=index[s['camera'],s['chain'],s['bit']-1];q=prev['V_record']['ports']['Q'];d=a['V_record']['ports']['D'];records={};table=[]
   for val in [0,1]:table.append({'Q':val,'actual_D':nl.value(d,{cb.norm(q):val},records)})
   r['stage_D_contract']={'previous_Q':q,'capture_D':d,'truth_table':table,'intermediate_V_models':records};r['checks']['D_previous_stage_identity']=all(t['actual_D']==t['Q'] for t in table)
  elif s['chain'] in {'ack_sync','req_sync','overrun_sync'}:
   src=s['first_stage_source_binding']['actual_Q'];r['first_stage_data_source']={'mapped_source_pin':src,'mapped_source_record':mg['primitives'][src.rsplit('/',1)[0]],'routed_D':a['routed_cell']+'/D','V_D':a['V_record']['ports']['D'],'state':'Exact graph alias/net binding in official_model_binding60_refined.json; upstream source-register transformed behavior remains independently reviewable.'}
  else:r['checks']['D_constant_zero']=a.get('constant_D_value')==0
  if s['chain'] in {'ack_sync','req_sync','overrun_sync'}:
   release,_=index[s['camera'],'cr' if s['chain']=='ack_sync' else 'hr',1];q=release['V_record']['ports']['Q'];sr=a['V_record']['ports']['SR'];records={};table=[]
   for val in [0,1]:table.append({'release_Q':val,'actual_SR':nl.value(sr,{cb.norm(q):val},records)})
   r['reset_release_contract']={'release_Q':q,'SR':sr,'truth_table':table,'intermediate_V_models':records};r['checks']['reset_release_identity']=all(t['actual_SR']==t['release_Q'] for t in table)
 except Exception as ex:r['errors'].append('Data/reset '+str(ex))
# Bind each boundary FF's actual exported path to its exact longest synthesis ancestor.
boundaries=[]
for boundary in binding['reset_boundary_models']:
 for ff in boundary['registered_boundaries']:
  origin=ff['logical_origin'];candidates=[c for c in sg['primitives'] if origin==c or origin.startswith(c+'/')]
  candidates=sorted(candidates,key=len,reverse=True)
  anchor=candidates[0] if candidates else None;rec=sg['primitives'].get(anchor);entry={'boundary':boundary['logical_boundary'],'camera':boundary['camera'],'actual_V_FF':ff,'synthesis_ancestor':anchor,'synthesis_record':rec,'synthesis_parameters':cb.parameters(rec) if rec else None,'synthesis_pin_connections':{p:sg['pin_net'].get(anchor+'/'+p) for p in rec['ports']} if rec else {},'exact_contract_limit':'Captured original GTP and actual V FF INIT/GRS/reset/enable and connections. Inversion, packing, and synchronous/asynchronous boundary transformations are not automatically accepted.'}
  routed_origin=origin.rsplit('/',2)[0];rcandidates=[c for c in g['primitives'] if routed_origin==c or routed_origin.startswith(c+'/')];rcandidates=sorted(rcandidates,key=len,reverse=True)
  if rcandidates:
   rc=rcandidates[0];entry.update(routed_ancestor=rc,routed_record=g['primitives'][rc],routed_parameters=cb.parameters(g['primitives'][rc]),routed_pin_connections={p:g['pin_net'].get(rc+'/'+p) for p in g['primitives'][rc]['ports']})
  boundaries.append(entry)
cb.save('stage_and_boundary_contract_evidence.json',{'rows60':out,'clock_identity_pass':sum(r['checks'].get('clock_identity',False) for r in out),'boundary_GTP_V_records':boundaries,'unresolved':[{'logical':r['logical'],'errors':r['errors'],'failed_checks':[k for k,v in r['checks'].items() if not v]} for r in out if r['errors'] or not all(r['checks'].values())],'official_cp_definition':'GRS low resets to INIT; otherwise C high clears to 0 / P high presets to 1; otherwise positive CLK samples D. V_FFASYN with CE=1 and exact SET_RESET/INIT/GRS/LRS matches this contract. See actual ModelSim receipts.','independent_boundary_transform_review_required':True})
print('CLOCK_PASS',sum(r['checks'].get('clock_identity',False) for r in out),'CONTRACT_ISSUE_ROWS',sum(bool(r['errors']) or not all(r['checks'].values()) for r in out),'BOUNDARY_FF_RECORDS',len(boundaries))
