"""物理 gop 网表精确绑定：不能将 routed gop 当作 synthesis GTP 解析。"""
import json
import generate_exact11 as gen
def main():
    path=gen.OUT/'routed/analysis/graph.json'
    if not path.exists():
        gen.write_json(gen.OUT/'coverageproof_routed.json',{'passed':False,'blocker':'尚无真实 routed 图，构建可能在早期失败'})
        return False
    g=json.loads(path.read_bytes());pr=g['primitives'];pn=g['pin_net']
    offline=json.loads((gen.OUT/'coverageproof_offline.json').read_bytes())
    synthesis=json.loads((gen.OUT/'coverageproof_synthesis.json').read_bytes()) if (gen.OUT/'coverageproof_synthesis.json').exists() else None
    errors=[];bindings=[];pairs=[];eliminated=[]
    sg=json.loads((gen.OUT/'actual/analysis/graph.json').read_bytes())
    required=[p for c in (synthesis['cameras'] if synthesis else offline['cameras']) for p in (c['actual']['leaves'] if synthesis else c['synthesis']['leaves'])]
    wanted={p.rsplit('/',1)[0] for p in required}|{p.rsplit('/',1)[0] for c in offline['cameras'] for pair in c['physical_pairs'] for p in pair}
    index={};physical_ancestors=set()
    for k,r in pr.items():
        ancestor=k
        while '/' in ancestor:
            ancestor=ancestor.rsplit('/',1)[0]
            physical_ancestors.add(ancestor)
            if ancestor not in wanted:continue
            for port in r['ports']:index.setdefault((ancestor,port),[]).append(k+'/'+port)
    absent={p.rsplit('/',1)[0] for p in required if not index.get(tuple(p.rsplit('/',1)))}
    def dead_cell(cell):
        queue=[cell];seen=set();cone=[]
        while queue:
            current=queue.pop()
            if current in seen:continue
            seen.add(current);rec=sg['primitives'][current];fan=[]
            assert current not in physical_ancestors,('缺失锥到达物理实例',cell,current)
            assert rec['type'].startswith(('GTP_DFF','GTP_LUT','GTP_INV','bmsKEEPBUF')),('未知缺失锥cell',current,rec['type'])
            for port,v in rec['ports'].items():
                if v['direction']!='OUTPUT':continue
                q=current+'/'+port;net=sg['pin_net'].get(q)
                if net is None:continue
                for alias in sg['net_aliases'][net]:
                    assert '/' in alias,('缺失锥到达顶层可观察端口',current,alias)
                for pin in sg['netpins'][net]:
                    k,p=pin.rsplit('/',1)
                    if sg['primitives'][k]['ports'][p]['direction']!='INPUT':continue
                    assert k not in physical_ancestors,('缺失寄存器锥有存活消费者',current,pin)
                    fan.append(pin);queue.append(k)
            cone.append({'cell':current,'type':rec['type'],'output_consumers':fan})
        return {'cell':cell,'cone':cone,'closed_sinkless_register_cone':True,'no_physical_or_top_observable_sink':True}
    dead_proofs={cell:dead_cell(cell) for cell in absent}
    def bind(logical):
        cell,port=logical.rsplit('/',1)
        candidates=index.get((cell,port),[])
        if not candidates and cell in dead_proofs and port=='CLK':
            eliminated.append({'logical':logical,'proof':dead_proofs[cell]});return None
        if len(candidates)!=1:
            errors.append({'logical':logical,'physical_candidates':candidates});return None
        p=candidates[0]
        if p not in pn:errors.append({'logical':logical,'unconnected':p});return None
        return p
    # 全部 camera 时钟叶节点精确落实到 routed 物理寄存器/DRM，无通配约束。
    for camera in offline['cameras']:
        actual_leaves=synthesis['cameras'][camera['camera']]['actual']['leaves'] if synthesis else camera['synthesis']['leaves']
        for logical in actual_leaves:
            physical=bind(logical)
            if physical:bindings.append({'logical':logical,'physical':physical,'type':pr[physical.rsplit('/',1)[0]]['type']})
        for a,b in camera['physical_pairs']:
            launch=bind(a);capture=bind(b)
            if not launch or not capture:continue
            q=launch.rsplit('/',1)[0]+'/Q'
            transparent=[]
            reached=q in pn and pn[q]==pn[capture]
            if q in pn and not reached:
                for pin in g['netpins'][pn[q]]:
                    k,p=pin.rsplit('/',1);rr=pr[k]
                    if rr['type']!='gopCLKROUTE' or p!='M' or k+'/CR' not in pn:continue
                    params={x[1]:x[-1] for x in (rr['parameters'] or rr['default_parameters']) if x[0]=='PARAMETER'}
                    values={name:int(v[1][-1].strip('"'),2) for name,v in params.items() if v[0]=='BITVEC'}
                    assert values=={'INITA':0,'INITB':(1<<64)-1,'INITC':0,'INITD':(1<<64)-1},('路由单元非恒等配置',k,values)
                    assert {p for p,v in rr['ports'].items() if v['direction']=='INPUT'}=={'M'}
                    if pn[k+'/CR']==pn[capture]:reached=True;transparent.append({'cell':k,'type':'gopCLKROUTE','input':pin,'output':k+'/CR','truth_configuration':values})
            if not reached:
                errors.append({'pair':[a,b],'physical':[launch,capture],'error':'mailbox Q 与 host D 不再直连'})
            else:pairs.append({'logical':[a,b],'physical':[launch,capture],'direct_Q_to_D':not transparent,'transparent_data_route':transparent})
    result={'passed':not errors and len(pairs)==1320,'physical_pair_count':len(pairs),'bindings':bindings,
            'pairs':pairs,'errors':errors,'eliminated_sinkless_registers':eliminated,'logical_leaf_count':len(required),
            'logical_leaf_accounted':len(bindings)+len(eliminated)==len(required),
            'method':'精确祖先绑定实际pin；Q->D允许经已核验恒等gopCLKROUTE；无物理实例只接受完整封闭无消费者寄存器锥实证，不猜gop为GTP'}
    gen.write_json(gen.OUT/'coverageproof_routed.json',result)
    print('实际 routed 覆盖核验：',result['passed'],'；物理对',len(pairs),'；错误',len(errors),flush=True)
    return result['passed']
if __name__=='__main__':main()
