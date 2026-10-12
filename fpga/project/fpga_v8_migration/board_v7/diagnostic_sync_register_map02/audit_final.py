"""Re-read real graphs; detailed endpoints and predecessor checks after controller completion."""
import collections, itertools, json, re
from pathlib import Path
import run as runner
from endpoint_logic import evaluate
HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
def save(n,v):runner.save(n,v)
def parameters(rec):
    vals={}
    for p in rec.get('default_parameters',[])+rec.get('parameters',[]):
        if len(p)>=3:
            node=p[-1]
            def leaf(v):
                if isinstance(v,list):return leaf(v[-1])
                return v.strip('"')
            vals[p[1]]=leaf(node)
    return vals
def detail(stage,g,a):
    pn=g['pin_net'];pr=g['primitives'];np=g['netpins'];aliases=g['net_aliases']
    bylogical={(r['camera'],r['chain'],r['bit']):r for r in a['rows']}
    def drivers(net):return [p for p in np.get(net,[]) if pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    def stripbuf(net):
        seen=set()
        while net not in seen:
            seen.add(net);ds=drivers(net)
            if len(ds)!=1:return net
            c=ds[0].rsplit('/',1)[0];r=pr[c]
            ins=[c+'/'+p for p,v in r['ports'].items() if v['direction']=='INPUT']
            index=re.search(r'\[\d+\]$',ds[0].rsplit('/',1)[1])
            if index:ins=[p for p in ins if p.endswith(index[0])]
            if 'BUF' in r['type'].upper() and len(ins)==1:net=pn[ins[0]]
            else:return net
        return net
    def constant(net):
        return evaluate(g,net,parameters)
    def netevidence(net):
        return {'net':net,'aliases':aliases.get(net,[]),'drivers':drivers(net),'driver_records':{p.rsplit('/',1)[0]:pr[p.rsplit('/',1)[0]] for p in drivers(net)}}
    out=[]
    for row in a['rows']:
        r=dict(row);r['checks']={}
        if len(row['cells'])!=1:
            out.append(r);continue
        c=row['cells'][0];rec=pr[c];params=parameters(rec)
        r['parameters_decoded']=params
        r['actual_input_cones']={p:netevidence(n) for p,n in row['pins'][c].items() if rec['ports'][p]['direction']=='INPUT' and n is not None}
        if not row['independent_endpoint_passed']:
            r['checks']['independent_cell_and_endpoints']=False;out.append(r);continue
        r['checks']['independent_cell_and_endpoints']=True
        dnet=pn.get(c+'/D');clknet=pn.get(row['clock_endpoints'][0]);rsnet=pn.get(row['reset_endpoints'][0])
        bit=row['bit'];cam=row['camera'];chain=row['chain']
        if bit:
            prev=bylogical[(cam,chain,bit-1)]
            prevnets=prev['matching_nets']
            r['checks']['D_is_previous_Q']=bool(dnet and any(stripbuf(dnet)==stripbuf(n) for n in prevnets))
        elif chain in {'cr','hr','reset_pipe'}:
            r['checks']['D_is_constant_zero']=constant(dnet)==0
        else:
            parent=f'source_diagnostics/cameras[{cam}].source'
            signal={'ack_sync':'ack','req_sync':'request','overrun_sync':'sticky_overrun'}[chain]
            nets=[n for n,als in aliases.items() if parent+'/@'+signal in als]
            if parent+'/'+signal+'/Q' in pn:nets.append(pn[parent+'/'+signal+'/Q'])
            nets.extend(pn[c+'/'+p] for c,rec in pr.items() if c.startswith(parent+'/'+signal+'/') for p,v in rec['ports'].items() if v['direction']=='OUTPUT' and p in {'Q','Q0'} and c+'/'+p in pn)
            r['original_input_actual_nets']=sorted(set(nets))
            r['checks']['D_is_original_first_stage_input']=bool(nets and any(stripbuf(n)==stripbuf(dnet) for n in nets))
        # Clock and reset are actual pin/net records; roots and sequential predecessors are explicitly recorded.
        root='cam_clk['+str(cam)+']' if chain in {'ack_sync','cr'} else 'clk'
        def upstream(net,seen=None):
            seen=set() if seen is None else seen
            if net in seen:return []
            seen.add(net)
            clocknames=['clk']+['cam_clk['+str(i)+']' for i in range(4)]
            ans=[n for n in clocknames if any(v in {'/'+n,'/@'+n,n} for v in aliases.get(net,[]))]
            for p in drivers(net):
                cc=p.rsplit('/',1)[0];rr=pr[cc]
                if 'DFF' in rr['type'].upper() or 'SRL' in rr['type'].upper():continue
                for pp,v in rr['ports'].items():
                    if v['direction']=='INPUT' and cc+'/'+pp in pn:ans+=upstream(pn[cc+'/'+pp],seen)
            return sorted(set(ans))
        roots=upstream(clknet)
        r['clock_root_expected']=root;r['clock_root_found']=roots
        r['checks']['clock_root_connected']=roots==[root]
        sync=chain in {'ack_sync','req_sync','overrun_sync'}
        if sync:
            resetrow=bylogical[(cam,'cr' if chain=='ack_sync' else 'hr',1)]
            r['checks']['reset_from_correct_release_stage']=any(stripbuf(rsnet)==stripbuf(n) for n in resetrow['matching_nets'])
        else:
            table=[{'rst':x,'cam_reset':y,'actual':evaluate(g,rsnet,parameters,{'rst':x,'cam_reset['+str(cam)+']':y}),'expected':x|y} for x,y in itertools.product([0,1],repeat=2)]
            r['reset_assertion_truth_table']=table
            r['checks']['reset_assertion_is_correct_active_high_OR']=all(v['actual']==v['expected'] for v in table)
        if rec['type'].startswith('GTP_DFF'):
            r['checks']['async_clear_or_set_correct']=('C' in rec['ports']) if sync else ('P' in rec['ports'])
            r['checks']['INIT_and_GRS']=params.get('INIT')==('0' if sync else '1') and params.get('GRS_EN')=='TRUE'
            if 'CE' in rec['ports']:r['checks']['CE_constant_one']=constant(pn[c+'/CE'])==1
        else:
            r['checks']['async_clear_or_set_correct']=params.get('FF_RS',params.get('FF0_RS'))==('RESET' if sync else 'SET') and params.get('RS_MODE')=='ASYNC'
            r['checks']['INIT_and_GRS']=params.get('FF_INIT',params.get('FF0_INIT'))==('0' if sync else '1') and params.get('GRS_EN')=='TRUE'
            r['checks']['positive_edge']=params.get('CLK_POL')=='FALSE'
            r['checks']['reset_polarity_and_enable']=params.get('LRS_POL')=='FALSE' and params.get('LRS_EN')=='TRUE'
            r['checks']['CE_constant_one_or_disabled']=params.get('LCE_EN')=='FALSE' or constant(pn.get(c+'/CE'))==1
        if stage=='mapping':
            attrs={a[1]:a[2:] for a in rec.get('attributes',[]) if len(a)>1}
            r['mapped_attributes']=attrs
            r['checks']['mapped_PAP_NOPRUNE_retained']=attrs.get('PAP_NOPRUNE')==[['BOOL','TRUE']]
        r['all_proven_checks_passed']=all(r['checks'].values());out.append(r)
    result={'stage':stage,'endpoint_status':a['status'],'rows':out,'failed_checks':[{k:r[k] for k in ['camera','chain','bit','checks']} for r in out if not r.get('all_proven_checks_passed',False)],'boundary':'PE asynchronous assertion cone evidence recorded per pin; no routed placement, recovery/removal, or timing acceptance inferred.'}
    save(stage+'_endpoint_details.json',result);return result
def main():
    assert (E/'final_result.json').exists(),'Wait for controller completion notification'
    results={};details={}
    for stage in ['compile','synthesis','mapping']:
        g=json.loads((E/stage/'analysis/graph.json').read_bytes())
        reference=json.loads((E/'synthesis/analysis/graph.json').read_bytes()) if stage=='mapping' else None
        a=runner.audit(stage,g,reference);results[stage]=a;details[stage]=detail(stage,g,a)
    receipt=json.loads((E/'final_result.json').read_bytes())
    receipt['stages']={k:{n:v[n] for n in ['status','independent_registers','independent_sync','independent_reset']} for k,v in results.items()}
    maplog=(E/'mapping.log').read_bytes()
    executed=[l.decode('ascii','backslashreplace') for l in maplog.splitlines() if b'Executing : dev_map ' in l]
    expected={'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0}
    options_proven=bool(executed) and all(any(re.search(r'-'+k+r'\s+0(?:\s|$)',l) for l in executed) for k in expected)
    receipt['mapping_option_evidence']={'executed_commands':executed,'expected':expected,'passed':options_proven}
    receipt['status']='PASS' if results['mapping']['status']=='PASS' and options_proven else 'FAIL'
    receipt['detail_failed_checks']={k:len(v['failed_checks']) for k,v in details.items()}
    receipt['physical_structure_passed']=results['mapping']['status']=='PASS'
    receipt['all_verified_checks_passed']=receipt['status']=='PASS' and all(not v['failed_checks'] for v in details.values())
    if not receipt['all_verified_checks_passed']:receipt['status']='FAIL'
    active=json.loads((E/'active_run_input_guard.json').read_bytes())
    bad=[p for p,h in active.items() if not Path(p).is_file() or runner.sha(Path(p))!=h]
    receipt['active_run_input_guard']={'count':len(active),'mismatches':bad}
    assert not bad,'Active run stable inputs changed'
    runner.verify()
    artifact_checks={}
    for stage in ['compile','synthesis','mapping']:
        artifact=json.loads((E/(stage+'_artifact.json')).read_bytes())
        artifact_checks[stage]={key:Path(artifact[key]).is_file() and runner.sha(Path(artifact[key]))==artifact[key+'_sha256'] for key in ['adf','native_db']}
        exported=json.loads((E/(stage+'_export_hashes.json')).read_bytes())
        artifact_checks[stage]['export_matches_artifact']=exported['adf_sha256']==artifact['adf_sha256']
        artifact_checks[stage]['graph_matches_export']=runner.sha(E/stage/'analysis/graph.json')==exported['graph_sha256']
        artifact_checks[stage]['dump_matches_export']=runner.sha(E/stage/'synthesis_export/synthesis_dump.txt')==exported['dump_sha256']
    receipt['artifact_hash_checks']=artifact_checks
    if not all(all(checks.values()) for checks in artifact_checks.values()):
        receipt['status']='FAIL';receipt['all_verified_checks_passed']=False
    save('independent_audit_result.json',{'status':receipt['status'],'mapping_options':receipt['mapping_option_evidence'],'artifact_hash_checks':artifact_checks,'active_run_input_guard':receipt['active_run_input_guard'],'failed_endpoint_checks':receipt['detail_failed_checks'],'auditor_sha256':runner.sha(Path(__file__)),'auditor_dependencies_sha256':{n:runner.sha(HERE/n) for n in ['endpoint_logic.py','run.py','analysis_tools/parse_objects.py']}})
    save('final_result.json',receipt)
    lines=['# Independent diagnostic register mapping experiment','',
           'Result: '+receipt['status']+'. Actual compile/synthesis/device-map graphs were exported and re-read. This experiment stops at device map; routed timing acceptance is not claimed.','',
           '| Stage | Independent sync / 28 | Independent reset / 32 | Endpoint result | ADF SHA256 | Native DB SHA256 |',
           '|---|---:|---:|---|---|---|']
    for stage in ['compile','synthesis','mapping']:
        art=json.loads((E/(stage+'_artifact.json')).read_bytes());r=results[stage]
        lines.append('| '+stage+' | '+str(r['independent_sync'])+' | '+str(r['independent_reset'])+' | '+r['status']+' | '+art['adf_sha256']+' | '+art['native_db_sha256']+' |')
    wrapper='A compact 32-bit stimulus wrapper drives four original 32-bit inputs through a 128-bit host-clock register; this is an isolated structural experiment.' if receipt.get('compact_stimulus') else 'A direct 43-port wrapper exposes the original inputs.'
    lines+=['',wrapper+' The real four-camera v7_sdt_bus and exact primitive candidate source bytes are retained. All 17 output groups connect to top outputs. Five roots: host 7.619 ns; cameras 11.905/11.905/20.833/20.833 ns. No timing exceptions or multicycle constraints. Required integer devmap_remove_dups=0, devmap_const_prop=0, devmap_control_set_num=0 are checked against the actual executed command. Options proven: '+str(options_proven)+'. Actual DB/constraint-context launch/result logs are retained.','',
            'Detailed physical cell types, parameter maps, real D/CLK/reset pin names, driver cones, logical Q aliases and per-stage predecessors are in evidence/*_topology.json and *_endpoint_details.json. Shared reset nets are allowed; shared storage cells are not. Compile/synthesis and mapped structure results are separate from official tool completion.','',
            'Protected production/old-IP guard: '+str(receipt['protected_count'])+' files checked; active integrated run stable inputs: '+str(len(active))+' files unchanged. No remote, programming, old IP changes, PNR, or bitstream generation. Input hashes are in evidence/input_hashes.json; copies preserve source GBK bytes.','']
    if receipt['status']=='FAIL':
        failed=[r for r in results['mapping']['rows'] if not r['independent_endpoint_passed']]
        packing={'status':'FAIL','independent_registers':results['mapping']['independent_registers'],'failed_bindings':failed,'required_options_proven':options_proven,'minimal_documented_comparison':'Apply syn_noprune=1 to only the 60 connected explicit GTP_DFF_CE/PE instances in a separate scoped comparison. ADS Synthesis User Guide PDF pages 90-91 supports instance scope. Preserve original evidence; recompile/synthesize/map and verify propagation plus all 60 unique storage endpoints. This is a candidate, not a proven anti-packing fix. syn_preserve is documented for module/port/register, not primitive-instance scope; syn_srlstyle concerns inferred shifts.','production_gate':'BLOCKED; no physical fix or routed timing signoff'}
        packing['minimal_documented_comparison']='This map02 already tests syn_noprune=1 on all 60 instances. Inspect actual propagation and packing witnesses. UCE PDF page 94 states FF packing ignores PAP_DONT_TOUCH; installed official docs provide no demonstrated anti-FF-pack fix.'
        save('packing_failure.json',packing)
        lines+=['Mapped physical independence FAIL. Explicit primitives did not establish all 60 independent storage/endpoints. Exact failed bindings:','']
        for row in failed:
            lines.append('- '+row['logical']+': '+', '.join(c+' ('+row['records'][c]['type']+')' for c in row['cells'])+'; output drivers '+str(row['drivers']))
        lines+=['','Next step: use these new ADF/graph/parameter records for vendor-supported packing control guidance. Do not guess packingdisable or integrate this candidate as a physical fix. A controlled topology change that inhibits packing must preserve mailbox/ACK/request cycles and asynchronous reset behavior, pass the same real-model regression, and then repeat isolated mapping. The documented attribute candidate may be a controlled comparison, but syn_srlstyle is not proof against SRL2 physical packing.']
        lines+=['',packing['minimal_documented_comparison']]
    else:
        lines+=['The small experiment proves mapped cell independence only. Recommended integration: create a new complete isolated top run, replace exactly the two candidate modules, retain these documented integer options, and repeat real compile/synthesis/map/routed endpoint and timing checks. Keep the active source_diagnostics_timing_build_01 project untouched. Any changed mapping names require deriving U-B and mailbox/complement constraints again from the new actual graphs, including both-corner 1320 mailbox budgets, all 364 retained clock-pair inheritance checks, and same-domain setup/hold plus reset recovery/removal. Do not reuse old leaf-name bindings.']
    lines+=['','Real-model baseline/candidate regression was completed in ../diagnostic_sync_register_timing_candidate/evidence/primitive_results.json. This mapping experiment does not repeat or broaden that regression. Detailed endpoint check failures: '+str(receipt['detail_failed_checks'])+'.','']
    (HERE/'REPORT.md').write_bytes('\n'.join(lines).encode('ascii'))
    chinese=['# '+HERE.name+' 真实 mapping 与独立审计','',
             '最终状态：'+receipt['status']+'。工具完成与物理结构通过分别核验。未执行 PNR、烧录或远程操作。','',
             '|阶段|独立存储单元 / 60|同步 / 28|复位 / 32|拓扑结果|','|---|---:|---:|---:|---|']
    for stage in ['compile','synthesis','mapping']:
        r=results[stage]
        chinese.append('|'+stage+'|'+str(r['independent_registers'])+'|'+str(r['independent_sync'])+'|'+str(r['independent_reset'])+'|'+r['status']+'|')
    chinese+=['','三个 devmap 整数选项的真实执行核验：'+str(options_proven)+'。',
              'ADF、native DB 与导出 graph 的 hash 核验：'+str(artifact_checks)+'。',
              '逐端点连接/属性检查失败数：'+str(receipt['detail_failed_checks'])+'。',
              '受保护工程与旧 IP 文件：'+str(receipt['protected_count'])+'；活动输入 guard：'+str(len(active))+' 个文件，差异 '+str(len(bad))+'。']
    if receipt['status']=='FAIL':
        chinese+=['','gate 不可放行。实际 packing 失败绑定见 evidence/packing_failure.json。',
                   '本 map02 已实际对照 60 个 syn_noprune=1 原语实例。官方 ADS 第 90–91 页支持 instance 作用域，但只说明综合保留。UCE PDF 第 94 页明确 FF pack 无视 PAP_DONT_TOUCH。当前不能据此宣称存在有效物理防 packing 属性，详见 COMPARISON_zh.md。']
        if (E/'packing_pair_witnesses.json').exists():
            witnesses=json.loads((E/'packing_pair_witnesses.json').read_bytes())
            assert all(runner.sha(E/s/'analysis/graph.json')==v for s,v in witnesses['graph_sha256'].items()),'Packing witness graph drift'
            chinese+=['','逐对实证见 evidence/packing_pair_witnesses.json：'+str(witnesses['packed_pairs'])+' 对，合成阶段 Q→D、同 clock、同异步 reset 与实际 mapped 物理单元绑定核验全部通过：'+str(witnesses['all_pair_proofs_passed'])+'。打包物理类型数量：'+str(witnesses['packed_physical_types'])+'。']
    chinese+=['','详证：evidence/final_result.json、independent_audit_result.json、mapping_artifact.json、mapping_topology.json、mapping_endpoint_details.json；字节逆变换和属性对照见 attribute_byte_inverse.json、attribute_propagation.json。']
    (HERE/'REPORT_zh.md').write_text('\n'.join(chinese)+'\n',encoding='utf-8')
    print('独立审计最终状态：'+receipt['status']+'；mapped 独立单元 '+str(results['mapping']['independent_registers'])+'/60；未获得完整证据不得放行。',flush=True)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
