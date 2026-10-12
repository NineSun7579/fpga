from pathlib import Path
import json,collections
HERE=Path(__file__).resolve().parent
def main():
    g=json.loads((HERE/'graph.json').read_bytes());o=json.loads((HERE/'objects.json').read_bytes())
    prim=g['primitives'];pn=g['pin_net'];np=g['netpins'];aliases=g['net_aliases']
    an={a:n for n,aa in aliases.items() for a in aa};drivers={n:[p for p in pp if prim[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT'] for n,pp in np.items()}
    def rec(pin):return {'pin':pin,'net':pn.get(pin),'drivers':drivers.get(pn.get(pin),[]),'aliases':[a for a in aliases.get(pn.get(pin),[]) if '/@' in a]}
    reset=[];chains=[];ordinary=[];negedge=[]
    for cam in range(4):
        pre=f'source_diagnostics/cameras[{cam}].source/'
        for signal,width in [('req_sync',3),('ack_sync',2),('overrun_sync',2)]:
            for i in range(width):
                ip=pre+f'{signal}[{i}]';assert ip in prim
                d=rec(ip+'/D');q=rec(ip+'/Q');c=rec(ip+'/CLK')
                expected=pre+f'{signal}[{i-1}]/Q' if i else pre+({'req_sync':'request','ack_sync':'ack','overrun_sync':'sticky_overrun'}[signal])+'/Q'
                assert d['drivers']==[expected],(ip,d)
                chains.append({'camera':cam,'signal':signal,'stage':i,'classification':'cdc_first' if i==0 else 'sync_later','cell':ip,'type':prim[ip]['type'],'D':d,'CLK':c,'Q_fanout':np[q['net']]})
                if i:ordinary.append({'classification':'sync_later','launch_CLK':expected.rsplit('/',1)[0]+'/CLK','capture_D':ip+'/D'})
        for signal in ['cr','hr']:
            for i in range(2):
                alias=an.get(pre+f'@{signal}[{i}]')
                outs=drivers.get(alias,[])
                merged_via=None
                if signal=='hr' and i==0 and not outs:
                    hr1=an[pre+'@hr[1]'];hr1q=drivers[hr1]
                    assert len(hr1q)==1
                    capture=hr1q[0].rsplit('/',1)[0]
                    outs=drivers[pn[capture+'/D']]
                    merged_via={'next_stage_Q':hr1q[0],'next_stage_D':capture+'/D','evidence':'actual first-stage Q drives actual hr[1] D; RTL hr shift equation'}
                reset.append({'camera':cam,'logical':f'{signal}[{i}]','actual_Q':outs,'merged':not any(p==pre+f'{signal}[{i}]/Q' for p in outs),'aliases':aliases.get(alias,[])})
                if merged_via:reset[-1]['merged_via']=merged_via
        for i in range(4):
            ip=f'source_diagnostics/cameras[{cam}].reset_pipe[{i}]'
            reset.append({'camera':cam,'logical':f'reset_pipe[{i}]','actual_Q':[ip+'/Q'],'D':rec(ip+'/D'),'CLK':rec(ip+'/CLK'),'P':rec(ip+'/P')})
    for ip,r in o['classified_registers'].items():
        if r['classification']=='negedge_binding':negedge.append({'cell':ip,'type':prim[ip]['type'],'CLK':rec(ip+'/CLK'),'D':rec(ip+'/D'),'Q':rec(ip+'/Q'),'parameters':prim[ip]['parameters']})
    result={'chains':chains,'reset':reset,'negedge':negedge,'ordinary_pairs':ordinary,'all_classified_registers':o['classified_registers'],
            'limits':['Recovery/removal/minimum pulse width remain unverified until timing reports','ASYNC_REG propagation and negedge inversion require STA/library confirmation']}
    (HERE/'classification.json').write_text(json.dumps(result,indent=2));print('chain registers',len(chains),'reset logical bits',len(reset),'negedge',len(negedge),'ordinary sync pairs',len(ordinary))
    print('host resets',[(r['camera'],r['logical'],r['actual_Q']) for r in reset if r['logical'].startswith('hr')])
if __name__=='__main__':main()
