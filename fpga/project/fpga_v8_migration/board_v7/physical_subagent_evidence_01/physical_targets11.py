"""根据当前routed图证明reset语义与SRL打包，并建立真实pin查询。"""
import json,re
import generate_exact11 as gen
def params(r):
    result={}
    for item in (r['parameters'] or r['default_parameters']):
        if item[0]!='PARAMETER':continue
        leaf=item[-1]
        if isinstance(leaf,list) and leaf:
            if leaf[0] in ('STRING','INTEGER'):result[item[1]]=leaf[1].strip('"')
            elif leaf[0]=='BIT':result[item[1]]=leaf[1][-1].strip('"')
    return result
def prepare(out=gen.OUT,route=None):
    route=route or gen.NEW/'place_route/v7_sdt_top_pnr.adf'
    proofpath=out/'coverageproof_routed.json';proof=json.loads(proofpath.read_bytes())
    assert proof['passed'],'物理 mailbox覆盖未通过'
    rg=json.loads((out/'routed/analysis/graph.json').read_bytes());sg=json.loads((out/'actual/analysis/graph.json').read_bytes())
    classification=json.loads((out/'actual/analysis/classification.json').read_bytes())
    reset_cells=sorted({q.rsplit('/',1)[0] for row in classification['reset'] for q in row['actual_Q']})
    groups={};errors=[]
    for logical in reset_cells:
        r=sg['primitives'][logical]
        ports=[p for p in r['ports'] if p in ('P','C','R','S')]
        if r['type'] not in ('GTP_DFF_P','GTP_DFF_C') or len(ports)!=1:
            errors.append({'unsupported_logical_reset':logical,'type':r['type'],'ports':ports});continue
        port=ports[0]
        exact=[k for k,v in rg['primitives'].items() if k.startswith(logical+'/') and 'RS' in v['ports']]
        packed_from=None
        if not exact:
            # 仅已实证两级直连、同CLK/异步入口/类型/INIT的相邻级可共享gopSRL2 RS。
            m=re.match(r'^(.*)\[(\d+)\]$',logical)
            if m and int(m[2])%2==1:
                first=m[1]+f'[{int(m[2])-1}]';fr=sg['primitives'].get(first)
                candidates=[k for k,v in rg['primitives'].items() if k.startswith(first+'/') and v['type'].startswith('gopSRL2') and 'RS' in v['ports']]
                if fr and len(candidates)==1:
                    assert fr['type']==r['type'] and params(fr)==params(r)
                    assert sg['pin_net'][first+'/Q']==sg['pin_net'][logical+'/D']
                    assert sg['pin_net'][first+'/CLK']==sg['pin_net'][logical+'/CLK']
                    assert sg['pin_net'][first+'/'+port]==sg['pin_net'][logical+'/'+port]
                    exact=candidates;packed_from=first
        if len(exact)!=1:errors.append({'unbound_reset':logical,'candidates':exact});continue
        physical=exact[0];pr=rg['primitives'][physical];pp=params(pr)
        expected='SET' if port=='P' else 'RESET'
        asserted_bits=['FF0_RS','FFAPP0_RS'] if pr['type'].startswith('gopSRL2') else ['FF_RS']
        valid=(pr['type'].startswith(('gopQ','gopSRL2')) and pp.get('RS_MODE')=='ASYNC' and pp.get('LRS_EN')=='TRUE'
               and pp.get('LRS_POL')=='FALSE' and all(pp.get(k)==expected for k in asserted_bits))
        if not valid:errors.append({'unproved_reset_semantics':logical,'physical':physical,'parameters':pp});continue
        # 精确逻辑异步网必须在物理RS网或RSCO传播链中出现，不把P->RS名字当证明。
        logical_aliases=set(sg['net_aliases'][sg['pin_net'][logical+'/'+port]])
        def canonical_alias(a):
            return a[2:] if a.startswith('/@') else a.replace('/@','/')
        wanted={canonical_alias(a) for a in logical_aliases if '/@' in a or '/' not in a}
        queue=[rg['pin_net'][physical+'/RS']];seen=set();common=set();trace=[]
        while queue:
            net=queue.pop()
            if net in seen:continue
            seen.add(net);common.update(wanted&{canonical_alias(a) for a in rg['net_aliases'][net]})
            if common:break
            for pin in rg['netpins'][net]:
                cell,p=pin.rsplit('/',1);rr=rg['primitives'][cell]
                if rr['ports'][p]['direction']!='OUTPUT':continue
                if p=='RSCO' and rr['type'].startswith(('gopQ','gopSRL2')) and cell+'/RS' in rg['pin_net']:
                    trace.append({'input':cell+'/RS','output':pin,'type':rr['type']});queue.append(rg['pin_net'][cell+'/RS'])
        if not common:errors.append({'reset_signal_provenance_missing':logical,'physical':physical+'/RS','logical_aliases':sorted(wanted),'trace':trace});continue
        rec={'logical':logical+'/'+port,'physical':physical+'/RS','type':pr['type'],'parameters':pp,
             'assertion_value':1 if port=='P' else 0,'shared_logical_aliases':sorted(common),'rsco_trace':trace,'packed_from':packed_from}
        groups.setdefault(physical+'/RS',[]).append(rec)
    bindings=[];internal=[];syncerrors=[]
    def bind(pin):
        cell,p=pin.rsplit('/',1);found=[k+'/'+p for k,r in rg['primitives'].items() if k.startswith(cell+'/') and p in r['ports'] and k+'/'+p in rg['pin_net']]
        return found[0] if len(found)==1 else None
    for row in classification['ordinary_pairs']:
        a=bind(row['launch_CLK']);b=bind(row['capture_D'])
        acell=row['launch_CLK'].rsplit('/',1)[0];bcell=row['capture_D'].rsplit('/',1)[0]
        if a and not b:
            pk=a.rsplit('/',1)[0];pr=rg['primitives'][pk];pp=params(pr)
            adjacent=re.sub(r'\[(\d+)\]$',lambda m:'['+str(int(m[1])+1)+']',acell)==bcell
            if pr['type'].startswith('gopSRL2') and adjacent and sg['pin_net'][acell+'/Q']==sg['pin_net'][bcell+'/D'] and sg['pin_net'][acell+'/CLK']==sg['pin_net'][bcell+'/CLK']:
                internal.append({'logical':[row['launch_CLK'],row['capture_D']],'packed_cell':pk,'type':pr['type'],'parameters':pp,
                                 'first_external_D':pk+'/D','shared_CLK':a,'connected_outputs':[pk+'/'+p for p,v in pr['ports'].items() if v['direction']=='OUTPUT' and pk+'/'+p in rg['pin_net']],
                                 'internal_stage_has_no_external_D_pin':True,'direct_two_stage_same_clock_proved':True})
                continue
        if not a:
            # second stage Q0/CLK of a verified packed primitive may launch to next external stage.
            match=re.match(r'^(.*)\[(\d+)\]$',acell)
            if match and int(match[2])%2==1:
                first=match[1]+f'[{int(match[2])-1}]';a=bind(first+'/CLK')
                if a and not rg['primitives'][a.rsplit('/',1)[0]]['type'].startswith('gopSRL2'):a=None
        if not a or not b:
            syncerrors.append({'logical':[row['launch_CLK'],row['capture_D']],'unbound':[a,b]});continue
        pc=a.rsplit('/',1)[0];rr=rg['primitives'][pc]
        outputs=[pc+'/'+p for p,v in rr['ports'].items() if v['direction']=='OUTPUT' and p in ('Q','Q0','CR0') and pc+'/'+p in rg['pin_net'] and rg['pin_net'][pc+'/'+p]==rg['pin_net'][b]]
        if len(outputs)!=1:
            syncerrors.append({'logical':[row['launch_CLK'],row['capture_D']],'physical':[a,b],'error':'sync 非直连'});continue
        bindings.append({'logical':[row['launch_CLK'],row['capture_D']],'physical':[a,b],'actual_data_output':outputs[0]})
    proof['route_sha256']=gen.cf.sha(route)
    proof['reset_bindings']=[{'physical':p,'logical_mappings':rows} for p,rows in sorted(groups.items())]
    proof['reset_logical_count']=len(reset_cells);proof['reset_binding_errors']=errors
    proof['reset_semantic_binding_passed']=not errors and sum(len(v) for v in groups.values())==len(reset_cells)
    proof['sync_bindings']=bindings;proof['sync_packed_internal']=internal;proof['sync_binding_errors']=syncerrors
    proof['sync_binding_passed']=not syncerrors and len(bindings)+len(internal)==len(classification['ordinary_pairs'])
    gen.write_json(proofpath,proof)
    gen.write_json(out/'physical_target_bindings.json',{'route_sha256':proof['route_sha256'],'pairs':proof['pairs'],
        'reset_bindings':proof['reset_bindings'],'sync_bindings':bindings,'sync_packed_internal':internal,'sync_binding_errors':syncerrors,
        'reset_semantic_binding_passed':proof['reset_semantic_binding_passed'],'errors':errors})
    return proof
if __name__=='__main__':
    p=prepare();print('reset semantic',p['reset_semantic_binding_passed'],'reset unique',len(p['reset_bindings']),'errors',p['reset_binding_errors'])
