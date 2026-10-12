from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,time
sys.dont_write_bytecode=True
import run_export as r
E=r.E;B=r.BOARD
def load(p):return json.loads(Path(p).read_bytes())
def main():
 before=load(E/'protection_before.json');now=r.inventory()
 r.save('protection_final.json',{'unchanged':before==now,'files':len(before),'changed':[p for p,h in before.items() if now.get(p)!=h],'added':sorted(set(now)-set(before))})
 old=load(B/'build04_mapped_endpoint_review02/before_hashes.json')
 r.save('review02_protected_inputs_recheck.json',{'files':len(old),'unchanged':all(Path(p).is_file() and r.sha(p)==h for p,h in old.items()),'changed':[p for p,h in old.items() if not Path(p).is_file() or r.sha(p)!=h]})
 w=E/'native_reparse';a=w/'analysis';a.mkdir(parents=True);d=w/'synthesis_export';d.mkdir()
 parser=B/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping/analysis/parse_objects.py'
 shutil.copy2(parser,a/'parse_objects.py');shutil.copy2(E/'native02/mapped_dump.txt',d/'synthesis_dump.txt')
 print('FRESH_NATIVE_PARSE_START',flush=True)
 run=subprocess.run([sys.executable,'-B',str(a/'parse_objects.py')],cwd=a,capture_output=True)
 (a/'parser.log').write_bytes(run.stdout+run.stderr)
 assert run.returncode==0
 original=B/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping/analysis/graph.json'
 graph=load(a/'graph.json');rows=load(B/'build04_mapped_endpoint_review02/rows60.json')['rows']
 checks=[]
 for row in rows:
  rec=graph['primitives'].get(row['cell'])
  checks.append({'cell':row['cell'],'type':row['type'],'site':row['planned_site'],'fresh_graph_matches_review02':rec==row['raw_record'],'official_behavior_bound':False})
 assert len(checks)==60
 r.save('fresh_native_graph_binding.json',{'input_adf_sha256':r.sha(E/'input'/r.SOURCE.name),'dump_sha256':r.sha(E/'native02/mapped_dump.txt'),'parser_original_sha256':r.sha(parser),'parser_copy_sha256':r.sha(a/'parse_objects.py'),'parser_exit_code':run.returncode,'graph_sha256':r.sha(a/'graph.json'),'original_graph_sha256':r.sha(original),'graph_byte_identical':r.sha(a/'graph.json')==r.sha(original),'rows':checks})
 raw=(E/'native02/mapped_dump.v').read_bytes();mods=re.findall(rb'\bmodule\s+(\S+)',raw)
 blocks=re.findall(rb'\bmodule\s+OPER\b(.*?)\bendmodule\b',raw,re.S)
 def empty(b):
  b=re.sub(rb'//[^\r\n]*',''.encode(),b)
  return b.split(b');',1)[1].strip()==b'' if b');' in b else False
 r.save('official_verilog_classification.json',{'file':str(E/'native02/mapped_dump.v'),'sha256':r.sha(E/'native02/mapped_dump.v'),'size':len(raw),'module_count':len(mods),'module_names':sorted({x.decode('ascii') for x in mods}),'operator_modules':len(blocks),'all_operator_bodies_empty':all(empty(x) for x in blocks),'V_FFASYN_tokens':raw.count(b'V_FFASYN'),'V_FFSYN_tokens':raw.count(b'V_FFSYN'),'V_LUT_tokens':raw.count(b'V_LUT'),'always_tokens':len(re.findall(rb'\balways\b',raw)),'assign_tokens':len(re.findall(rb'\bassign\b',raw)),'behavioral_binding':False})
 models=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim')
 r.save('official_readable_model_hashes.json',{str(models/n):r.sha(models/n) for n in ['V_FFASYN.v','V_FFSYN.v','V_LUT5.v','V_MUX2LUT6.v','INT_LUTMUX2_UDP.v','INT_LUTMUX4_UDP.v']})
 native=load(E/'native02_receipt.json');functional=load(E/'functional01_receipt.json')
 r.save('final_result.json',{'status':'BLOCKED_OFFICIAL_MAPPED_BEHAVIOR_BINDING','native_export_exit_code':native['exit_code'],'functional_export_exit_code':functional['exit_code'],'functional_export_blocker':'Flow-0013: input DB should be of phase PNR','official_v_is_operator_blackbox':True,'distinct_storage_structure_preexisting':60,'behavior_bound_storage':0,'source_resetcone_behavior_bound':False,'protection_unchanged':before==now,'review02_protected_inputs_unchanged':all(Path(p).is_file() and r.sha(p)==h for p,h in old.items()),'original_FAIL_retained':True,'compile':False,'mapping':False,'pnr':False,'bit':False,'board':False,'independent_review03':'pending external reviewer; handoff only','minimum_support_interface':'Official MAP-phase gop->verification V_* exporter preserving exact parameters/pin connectivity (including source resetcone registered/inverted outputs), or official documented readable semantics for the exact gop variants. Existing gen_netlist requires PNR phase; no phase rewriting permitted.'})
 r.save('review03_bundle_hashes.json',{str(p.relative_to(E)):r.sha(p) for p in E.rglob('*') if p.is_file() and p.name!='review03_bundle_hashes.json'})
 print('SEAL_FINISH BLOCKED no behavioral PASS',flush=True)
if __name__=='__main__':main()
