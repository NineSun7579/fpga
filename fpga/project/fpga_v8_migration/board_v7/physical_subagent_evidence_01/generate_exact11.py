"""离线最小修正：冻结 V7 的 U-B，透明时钟图全覆盖；不触碰运行工程。"""
from pathlib import Path
import json,re,hashlib
import continue_fixed as cf
ROOT=Path(__file__).resolve().parent/'fixed_06'
OUT=ROOT/'physical_exact_11'
OLD=cf.BASE/'source_diagnostics_route_02'
NEW=cf.BASE/'source_diagnostics_route_03'
def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def native(pin):
    cell,port=pin.rsplit('/',1)
    return cell.replace('/','.')+'/'+port
def coll(pins):
    assert pins
    return '[get_pins -hierarchical {'+' '.join(native(x) for x in sorted(set(pins)))+'}]'
def transparent(record):
    t=record['type']
    return t in ('bmsWIDEBUF','bmsWIDEINV','bmsBUF','bmsINV','GTP_INV','GTP_INBUF','GTP_CLKBUFG','GTP_CLKBUF','GTP_CLKBUFH') or t.startswith('bmsKEEPBUF_Cell_')
def camera_leaves(g,camera):
    """从真实顶层根网出发，透明输入/输出双向展开；未知时钟接收者即失败。"""
    prim,pn,np=g['primitives'],g['pin_net'],g['netpins']
    name=f'cmos{camera+1}_pclk'
    roots={n for n,a in g['net_aliases'].items() if name in a or '/@'+name in a}
    assert len(roots)==1,(name,roots)
    queue=list(roots);seen=set();leaves=set();edges=[];unknown=[]
    while queue:
        net=queue.pop()
        if net in seen:continue
        seen.add(net)
        for pin in np[net]:
            cell,port=pin.rsplit('/',1);r=prim[cell];v=r['ports'][port]
            if transparent(r):
                # 单位宽/逐位直通，不允许多控制口时钟门控偷偷作为透明对象。
                inputs=[p for p,x in r['ports'].items() if x['direction']=='INPUT']
                outputs=[p for p,x in r['ports'].items() if x['direction']=='OUTPUT']
                assert len(inputs)==len(outputs)==1,(cell,r['type'],inputs,outputs)
                linked=[cell+'/'+p for p in inputs+outputs]
                edges.append({'cell':cell,'type':r['type'],'pins':linked,'unconnected':[p for p in linked if p not in pn]})
                queue.extend(pn[p] for p in linked if p in pn)
            elif v['direction']=='INPUT':
                allowed=r['type'].startswith(('bmsWIDEDFF','GTP_DFF','GTP_DRM'))
                if v['clock'] and allowed:leaves.add(pin)
                else:unknown.append({'pin':pin,'type':r['type'],'clock':v['clock']})
    assert not unknown,unknown
    assert leaves
    return {'clock':name,'roots':sorted(roots),'nets':sorted(seen),'leaves':sorted(leaves),
            'transparent':list({x['cell']:x for x in edges}.values()),'unknown':unknown}
def frozen_universe(raw):
    text=raw.decode('ascii')
    active=[s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
    clocks=set();groups=[]
    for s in active:
        if s.startswith(('create_clock ','create_generated_clock ')):
            clocks.add(re.search(r'-name\s+\{([^}]+)\}',s)[1])
        if s.startswith('set_clock_groups '):
            assert '-asynchronous' in s
            gs=re.findall(r'-group\s+\[get_clocks\s+\{?([\w]+)\}?\]',s)
            assert len(gs)==1,s
            groups.append(gs[0])
    assert set(groups)<=clocks
    universe={(a,b) for a in clocks for b in clocks if a!=b and (a in groups or b in groups)}
    carved={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
    assert carved<=universe
    return clocks,groups,universe,carved
def main():
    OUT.mkdir(exist_ok=True)
    frozen=OLD/'inputs/source/constraints/clock.fdc'
    raw=frozen.read_bytes();clocks,groups,u,carved=frozen_universe(raw)
    cg=json.loads((ROOT/'native_probe_07/compile_actual/analysis/graph.json').read_bytes())
    sg=json.loads((ROOT/'physical_exact_09/actual/analysis/graph.json').read_bytes())
    exact=json.loads((ROOT/'physical_exact_09/actual/analysis/exact_complement.json').read_bytes())
    assert not exact['errors']
    base=b'\n'.join(s for s in raw.splitlines() if not s.lstrip().startswith(b'set_clock_groups '))+b'\n'
    lines=['# Frozen V7 complete directed asynchronous U minus four mailbox budgets B; no global async.']
    for a,b in sorted(u-carved):
        lines.append(f'set_false_path -from [get_clocks {{{a}}}] -to [get_clocks {{{b}}}]')
    evidence=[]
    for c in exact['cameras']:
        i=c['camera'];cp=camera_leaves(cg,i);sp=camera_leaves(sg,i)
        pre=f'source_diagnostics/cameras[{i}].source/'
        mb={k+'/CLK' for k in cg['primitives'] if k.startswith(pre+'mailbox[')}
        host={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(pre+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        assert len(mb)==17 and len(host)==512
        assert mb<=set(cp['leaves'])
        sm=set(c['mailbox_launch_pins']);sc=set(c['complement_launch_pins'])
        assert set(sp['leaves'])==sm|sc and not sm&sc
        comp=set(cp['leaves'])-mb
        assert any('src_snapshot[' in p for p in comp) and any('dbg_href_raw[' in p for p in comp)
        launches=mb|sm;captures=host|set(c['capture_D'])
        assert len(c['bundle_pairs'])==330
        lines.extend(['set_false_path -from '+coll(comp|sc)+' -to [get_clocks {ddrphy_sysclk}]',
                      'set_max_delay -datapath_only 15.238 -from '+coll(launches)+' -to '+coll(captures),
                      'set_false_path -hold -from '+coll(launches)+' -to '+coll(captures)])
        # ACK 首级仅精确端点；后一同步级仍是同域时序。保存直接 Q->D 拓扑证据。
        ack=pre+'ack';first=pre+'ack_sync[0]';later=pre+'ack_sync[1]'
        assert sg['pin_net'][ack+'/Q']==sg['pin_net'][first+'/D']
        assert sg['pin_net'][first+'/Q']==sg['pin_net'][later+'/D']
        assert sg['pin_net'][first+'/CLK']==sg['pin_net'][later+'/CLK']
        assert sg['pin_net'][ack+'/CLK']!=sg['pin_net'][first+'/CLK']
        lines.append('set_false_path -from '+coll({ack+'/CLK'})+' -to '+coll({first+'/D',pre+'ack_sync[1:0]/D[0]'}))
        evidence.append({'camera':i,'compile':cp,'synthesis':sp,'compile_mailbox':sorted(mb),
                         'compile_complement':sorted(comp),'physical_pairs':c['bundle_pairs'],
                         'ack_first':[ack+'/CLK',first+'/D'],'ack_same_domain_later':[first+'/CLK',later+'/D']})
    # 只生成独立证据文件；实际运行器闲置后才创建 route03。
    generated=base+'\n'.join(lines).encode('utf8')+b'\n'
    (OUT/'clock.fdc').write_bytes(generated)
    assert b'set_clock_groups ' not in b'\n'.join(s for s in generated.splitlines() if not s.lstrip().startswith(b'#'))
    write_json(OUT/'coverageproof_offline.json',{'frozen_clock_fdc':str(frozen),'sha256':cf.sha(frozen),
        'clocks':sorted(clocks),'original_groups':groups,'old_U':sorted(u),'retained_clock_pairs':sorted(u-carved),
        'carved_camera_to_ddr':sorted(carved),'all_old_pairs_accounted':(u-carved)|carved==u,
        'same_domain_exemptions':[],'mailbox_budget_ns':15.238,'physical_pairs':1320,'cameras':evidence,
        'runtime_proven':False,'remote_or_program':False})
    guard=json.loads((cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    bad=[p for p,h in guard.items() if cf.sha(Path(p))!=h]
    write_json(OUT/'protected_offline.json',{'count':len(guard),'mismatches':bad})
    assert len(guard)==1022 and not bad
    print('离线修正验证完成：完整 U-B；1320 对 15.238ns；1022 保护哈希不变。',flush=True)
if __name__=='__main__':main()
