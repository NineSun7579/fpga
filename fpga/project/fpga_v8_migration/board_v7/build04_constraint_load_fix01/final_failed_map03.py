"""Audit completed real MAP; deliver failure without weakening qualification gates."""
import sys,json,re,tkinter,collections,time
sys.dont_write_bytecode=True
import runner as r
r.E=r.E/'rebuild03';r.W=r.E/'candidate02'
from native_audit import pairs,cdb,messages
from binding_review import sexpr,fields
def main():
 receipts={}
 for label in ['compile02','compile_native_export','synthesize02','synthesis_native_export','mapping02','mapping_native_export']:
  p=r.E/(label+'_receipt.json');rec=json.loads(p.read_bytes());assert rec['rc']==0 and not rec['errors'];receipts[label]={'receipt_sha256':r.sha(p),'rc':rec['rc'],'errors':rec['errors']}
 gf=r.E/'mapping_native/analysis/graph.json';g=json.loads(gf.read_bytes());pp=pairs(g,1284)
 raw=cdb('mapping_native');root=sexpr(raw)
 mm={fields(n)['CDBID'][0]:fields(n) for n in root[1:] if isinstance(n,list) and n and n[0]=='MMD' and fields(n).get('DELAY')==['15238']}
 assert len(mm)==4 and all(f.get('DATAPATH_ONLY')==['1'] for f in mm.values())
 assert not re.search(rb'\(CLKGP\b',raw)
 bound=[];residual=[]
 for p in pp:
  def annotations(pin,typ):
   cell,port=pin.rsplit('/',1)
   return {f['CDBID'][0] for n in g['primitives'][cell]['cdb_entries'] for f in [fields(n)] if f.get('PINNAME')==[port] and f.get('TYPE')==[typ] and f.get('CDBID',[''])[0] in mm}
  shared=annotations(p['launch_CLK'],'1')&annotations(p['capture_D'],'3')
  row={**p,'budget_CDBIDs':sorted(shared)}
  if int(re.search(r'/host_bank\[(\d+)\]',p['capture_D'])[1])<480:
   assert len(shared)==1;bound.append(row)
  else:
   assert not shared;residual.append(row)
 assert len(bound)==1280 and len(residual)==4
 assert all(len({p['budget_CDBIDs'][0] for p in bound if p['camera']==cam})==1 for cam in range(4))
 t=tkinter.Tcl();draft=r.W/'constraints_live/production60.lcf';pcf=r.W/'device_map/v7_sdt_top.pcf'
 targets=[t.splitlist(l) for l in draft.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
 locations=[t.splitlist(l) for l in pcf.read_text().splitlines() if l.startswith('def_inst_site ')]
 srows=[]
 for cmd in targets:
  source=cmd[1][2:];cs=[c for c in g['primitives'] if c==source or c.startswith(source+'/')];assert len(cs)==1
  cell=cs[0];v=g['primitives'][cell];entry=[p for p in locations if p[1].lstrip('\\')==cell]
  attrs=[a for a in v['attributes'] if a[0]=='ATTRIBUTE' and a[1]=='PAP_LOC']
  srows.append({'source':source,'cell':cell,'type':v['type'],'required_site':cmd[3],'PCF':entry,'native_PAP_LOC':attrs,'site_match':len(entry)==1 and entry[0][2]==cmd[3],'exact_gopQ':v['type']=='gopQ','ports':v['ports'],'parameters':v['parameters'],'default_parameters':v['default_parameters']})
 assert len(srows)==len({p['cell'] for p in srows})==len({p['required_site'] for p in srows})==60
 source=json.loads((r.E/'sourcehash.json').read_bytes());assert len(source['hashes'])==741 and source['registered']==186
 assert all(r.sha(r.W/n)==h==r.sha(r.B/n) for n,h in source['hashes'].items())
 registration=json.loads((r.E/'registration186.json').read_bytes());assert len(registration)==186
 clocks={n[1].strip('"'):fields(n) for group in root[1:] if isinstance(group,list) and group and group[0]=='CLOCK' for n in group[1:] if isinstance(n,list) and n and n[0]=='CLOCK'}
 assert clocks['free_clk']['PERIOD']==['40000/1']
 assert clocks['ddrphy_sysclk']['SOURCE']==['"free_clk"'] and clocks['ddrphy_sysclk']['MUL_FAC']==['84'] and clocks['ddrphy_sysclk']['DIV_FAC']==['16']
 assert 25*84/16==131.25
 messages();r.guard()
 typecounts=dict(collections.Counter(x['type'] for x in srows))
 result={'status':'FAIL_FRESH_MAP_QUALIFICATION','actual_phase':'MAP_COMPLETE_NOT_QUALIFIED','receipts':receipts,'actual_total_pairs':1284,'required_total_pairs':1280,'native_budget_bound_dynamic_pairs':1280,'budget_ns':15.238,'budget_entries':mm,'budget_bound_rows':bound,'extra_unannotated_signature_rows':residual,'old_CLKGP_present':False,'source741_byte_equal':True,'registered186':True,'mapped60':srows,'mapped60_types':typecounts,'site_matches':sum(x['site_match'] for x in srows),'exact_gopQ_count':sum(x['exact_gopQ'] for x in srows),'graph_sha256':r.sha(gf),'CDB_sha256':r.sha(r.E/'mapping_native_CDB_raw.txt'),'mapADF':str(r.W/'device_map/v7_sdt_top_map.adf'),'mapADF_sha256':r.sha(r.W/'device_map/v7_sdt_top_map.adf'),'PCF_sha256':r.sha(pcf),'PNR_started':False,'global10_measured':False,'old_timing_failures_ns':{'Setup':-0.071,'Hold':-1.711,'Removal':-0.038},'bit_generated':False,'remote_operation':False,'qualification_gates_relaxed':False,'blocker':'Actual mapped total 1284 differs from required 1280; native storage types are separately recorded. No supported remedy has been verified under unchanged RTL, preserved attributes and disabled mapping optimizations.'}
 assert not (r.E/'route_attempt01').exists(),'Unexpected PNR attempt'
 r.save('FINAL_REAL_MAP_RESULT.json',result)
 r.save('actual_review_handoff.json',{'status':result['status'],'result':str(r.E/'FINAL_REAL_MAP_RESULT.json'),'actual_pairs':1284,'required_pairs':1280,'budget_bound_pairs':1280,'site_matches':result['site_matches'],'mapped60_types':typecounts,'PNR_started':False,'bit':False,'remote':False,'blocker':result['blocker']})
 doc='本轮真实结果：FAIL_FRESH_MAP_QUALIFICATION\n\ncompile/synthesis/map及原生导出全部rc=0、errors=0。新mapped CDB确有4条15238ps datapath-only预算，逐对绑定1280动态关系；无旧CLKGP。\n\n完整mapped图有1284 unique，要求1280，未通过。多出的4条是每路host_bank[480] ← mailbox[480]/Q；mailbox D接原生常量1，launch/capture无预算注解。本轮保留这些真实对象，没有删掉计数，也没有为它们加falsepath。\n\nproduction60：60个独立sourcepath/site，PCF精确命中'+str(result['site_matches'])+'/60；mapped类型 '+json.dumps(typecounts)+'；原exact gopQ gate通过'+str(result['exact_gopQ_count'])+'/60，未放宽其类型检查。详细ports、params、PAP_LOC、PCF见FINAL_REAL_MAP_RESULT.json。\n\n源码741与冻结build04逐文件字节一致，登记186，冻结保护drift=0。官方remove_dups/const_prop/control_set_num=0保持。\n\nPNR未启动，global10未实测；旧Setup -0.071、Hold -1.711、Removal -0.038仍为失败事实。未bit、未远端操作。当前只能交付失败的真实fresh map，不能声明可用PNR输入或时序修复PASS。后续需要验证能在既定保持要求下消除残留签名storage并恢复60目标存储模型的官方流程；目前无该成功证据。\n'
 (r.E/'RESULT_ZH.md').write_text(doc,encoding='utf-8')
 print(doc,flush=True)
if __name__=='__main__':main()
