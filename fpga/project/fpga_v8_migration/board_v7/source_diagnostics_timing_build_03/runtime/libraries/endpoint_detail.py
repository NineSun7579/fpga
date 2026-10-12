import itertools, re
from endpoint_logic import evaluate
from preflight import save


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

