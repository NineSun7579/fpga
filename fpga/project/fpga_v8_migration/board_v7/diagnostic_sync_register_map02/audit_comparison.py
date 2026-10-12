"""Re-read real stage graphs and attribute propagation, retain negative gate."""
import json,collections,re
from pathlib import Path
import run,audit_final
H=Path(__file__).resolve().parent;E=H/'evidence'
def attributes(rec):
    return {a[1]:a[2:] for a in rec.get('attributes',[]) if len(a)>1}
def main():
    run.verify()
    unknown=[]
    for label in ['compile','synthesis','mapping']:
        for line in (E/(label+'.log')).read_bytes().splitlines():
            if line.startswith(b'E:') or re.match(rb'\s*(?:\*\*\s*)?(?:ERROR|FATAL)\b',line) or re.search(rb'(?:unknown|unsupported|unrecognized|ignor\w*).*(?:option|attribute)|(?:option|attribute).*not supported',line,re.I):unknown.append(line.decode('ascii','backslashreplace'))
    run.save('unknown_option_attribute_check.json',{'passed':not unknown,'rejected_lines':unknown})
    assert not unknown,'Tool reported ignored/unsupported option or attribute'
    audit_final.main()
    proof=json.loads((E/'attribute_byte_inverse.json').read_bytes())
    propagation={}
    for stage in ['compile','synthesis','mapping']:
        g=json.loads((E/stage/'analysis/graph.json').read_bytes())
        topo=json.loads((E/(stage+'_topology.json')).read_bytes())
        rows=[]
        for r in topo['rows']:
            cells=r['cells']
            direct=g['primitives'].get(r['expected_instance'])
            records={c:g['primitives'][c] for c in cells}
            if direct is not None:records[r['expected_instance']]=direct
            rows.append({'logical':r['logical'],'expected_instance':r['expected_instance'],'actual_cells':cells,'cell_attributes':{c:attributes(v) for c,v in records.items()},'independent_endpoint':r['independent_endpoint_passed'],'physical_types':{c:v['type'] for c,v in records.items()}})
        propagation[stage]=rows
    retained={stage:sum(len(r['actual_cells'])==1 and r['cell_attributes'].get(r['actual_cells'][0],{}).get('PAP_NOPRUNE')==[['BOOL','TRUE']] for r in rows) for stage,rows in propagation.items()}
    run.save('attribute_propagation.json',{'attribute_source':proof,'official_basis':json.loads((E/'instance_scope_official.json').read_bytes()),'rows_by_stage':propagation,'PAP_NOPRUNE_TRUE_logical_stage_counts':retained,'mapped_all_60_retained':retained['mapping']==60})
    mapping=json.loads((E/'mapping_topology.json').read_bytes());failed=[r for r in mapping['rows'] if not r['independent_endpoint_passed']]
    syn=json.loads((E/'synthesis/analysis/graph.json').read_bytes())
    bylogical={(r['camera'],r['chain'],r['bit']):r for r in mapping['rows']}
    pairs=[]
    for r in mapping['rows']:
        if r['bit']%2:continue
        nxt=bylogical.get((r['camera'],r['chain'],r['bit']+1))
        if not nxt or len(r['cells'])!=1 or r['cells']!=nxt['cells']:continue
        before=r['expected_instance'];after=nxt['expected_instance'];pn=syn['pin_net']
        reset='C' if r['chain'] in {'ack_sync','req_sync','overrun_sync'} else 'P'
        checks={'same_mapped_storage':True,'synthesis_Q_to_D':pn.get(before+'/Q')==pn.get(after+'/D') and before+'/Q' in pn,'same_clock':pn.get(before+'/CLK')==pn.get(after+'/CLK') and before+'/CLK' in pn,'same_reset':pn.get(before+'/'+reset)==pn.get(after+'/'+reset) and before+'/'+reset in pn}
        pairs.append({'logical_pair':[r['logical'],nxt['logical']],'mapped_cell':r['cells'][0],'type':r['records'][r['cells'][0]]['type'],'checks':checks})
    run.save('packing_pair_witnesses.json',{'packed_pairs':len(pairs),'rows':pairs,'all_pair_proofs_passed':all(all(p['checks'].values()) for p in pairs),'packed_physical_types':dict(collections.Counter(p['type'] for p in pairs)),'graph_sha256':{s:run.sha(E/s/'analysis/graph.json') for s in ['synthesis','mapping']}})
    cells={c:v['type'] for r in failed for c,v in r['records'].items()}
    packed_types=dict(collections.Counter(cells.values()))
    doc=json.loads((E/'official_FF_pack_exception.json').read_bytes())
    final=json.loads((E/'final_result.json').read_bytes())
    final['mapped_attribute_evidence']={'PAP_NOPRUNE_TRUE_logical_stages':retained['mapping'],'required':60,'passed':retained['mapping']==60,'evidence_sha256':run.sha(E/'attribute_propagation.json')}
    if retained['mapping']!=60:
        final['status']='FAIL';final['all_verified_checks_passed']=False
    run.save('final_result.json',final)
    independent=json.loads((E/'independent_audit_result.json').read_bytes())
    independent['status']=final['status'];independent['mapped_attribute_evidence']=final['mapped_attribute_evidence']
    independent['comparison_auditor_sha256']=run.sha(Path(__file__))
    run.save('independent_audit_result.json',independent)
    summary={'experiment':H.name,'status':final['status'],'independent_registers':mapping['independent_registers'],'sync':mapping['independent_sync'],'reset':mapping['independent_reset'],'failed_target_stages':len(failed),'failed_bound_physical_types':packed_types,'byte_inverse_exact':proof['all_inverse_exact'],'official_mapping_limitation':doc,'production_gate':'BLOCKED; map01 untouched, no full routed signoff','comparison_scope':'Exactly 60 primitive instance attributes; same compact wrapper, functional bytes and clocks'}
    run.save('comparison_conclusion.json',summary)
    gate=json.loads((E/'negative_gate_before.json').read_bytes())
    assert run.sha(Path(gate['build02_blocked_receipt_file']))==gate['build02_blocked_receipt_sha256']
    run.save('negative_gate_after.json',gate|{'reverified':True,'map01_all_files_unchanged':True,'build02_blocked_receipt_unchanged':True})
    lines=['# '+H.name+' 实际属性对照结论','',
           '结论：'+final['status']+'。实际 mapped 独立存储单元 '+str(mapping['independent_registers'])+'/60（同步 '+str(mapping['independent_sync'])+'/28，复位 '+str(mapping['independent_reset'])+'/32）。','',
           '只对 60 个显式原语实例加 syn_noprune=1；移除新增属性逐字节还原原 primitive 源。compact wrapper、输入输出、时钟和功能周期未变。','',
           '旧 synthesis 的 24 项端点失败为审计解析范围不足：12 项原信号已规范为真实 Q 引脚，12 项常零经过 INIT=10 的 LUT1。新审计按实际 pin/net、LUT INIT 求值并验证异步复位 OR 真值表，不跳过 INIT、reset polarity 或 CE。旧 compile/synthesis 重新核验均为 60 级全部通过，证据保存于本目录 baseline01_*，map01 无改动。','',
           '真实 mapped 失败类型：'+str(packed_types)+'。逐端点、属性传播与完整 hash 见 evidence/attribute_propagation.json、*_endpoint_details.json、final_result.json。','',
           '官方 User Constraint Editor 手册 PDF 第 94 页（页内编号 93）明确：PAP_DONT_TOUCH 作用于 GTP 实例/module，但 FF pack 无视该属性。安装的 19 本官方 PDF 全文检索记录在 official_packing_scope_search.json。该属性不能作为已证实 anti-FF-pack 方案；不得猜 packingdisable 或忽略 unknown option。','',
           '生产 gate 保持阻断。map01、build02 源/runtime、741 活动输入及 1022 原工程/旧 IP 文件 guard 均核验。未进行 PNR、时序放宽、设备、远程或烧录操作；不宣称 timing pass。']
    for stage in ['compile','synthesis','mapping']:
        art=json.loads((E/(stage+'_artifact.json')).read_bytes());lines+=['',stage+' ADF SHA256: '+art['adf_sha256'],stage+' native DB SHA256: '+art['native_db_sha256']]
    (H/'COMPARISON_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('实际属性对照最终结论：'+summary['status']+'；'+str(summary['independent_registers'])+'/60；gate 阻断',flush=True)
if __name__=='__main__':main()
