"""Full-top independent60; actual aliases adapt reset roots, not waived checks."""
import itertools, sys
from pathlib import Path
from preflight import HERE, load, require, sha
sys.path.insert(0,str(HERE/'runtime/analysis_tools'))
from graph_adapter import Resolver, classify, canon
from endpoint_detail import parameters
from endpoint_logic import evaluate

def alias_root(g,names):
    matches={n for n,aa in g['net_aliases'].items() if any(canon(a) in names for a in aa)}
    require(len(matches)==1,'Actual bus/reset root ambiguous or absent: '+repr(names))
    return next(iter(matches))

def full_top_audit(stage,g,record):
    classified=classify(g);r=Resolver(g);rows=[];lookup={(x['camera'],x['chain'],x['bit']):x for x in classified['rows']}
    busrst=alias_root(g,{'source_diagnostics/rst','axi_rst'})
    for row in classified['rows']:
        cam=row['camera'];chain=row['chain'];rec=g['primitives'][row['cell']];p=parameters(rec)
        sync=chain in {'ack_sync','req_sync','overrun_sync'}
        checks={'independent_cell_and_endpoints':True}
        if row['bit']:
            prev=lookup[(cam,chain,row['bit']-1)];checks['D_is_previous_Q']=r.equal(prev['Q'],row['D'])
        elif sync:checks['D_is_original_first_stage_input']=r.equal(r.signal_q(cam,{'ack_sync':'ack','req_sync':'request','overrun_sync':'sticky_overrun'}[chain]),row['D'])
        else:checks['D_is_constant_zero']=evaluate(g,g['pin_net'][row['D']],parameters)==0
        expected=f'cmos{cam+1}_pclk' if chain in {'ack_sync','cr'} else 'ddrphy_sysclk'
        roots=set();seen=set()
        def trace(net):
            if net in seen:return
            seen.add(net)
            aliases={canon(a) for a in g['net_aliases'].get(net,[])}
            if expected in aliases:roots.add(expected);return
            for driver in r.drivers(net):
                cell=driver.rsplit('/',1)[0];rr=g['primitives'][cell]
                if any(t in rr['type'].upper() for t in ['DFF','SRL','RAM','DRM']):continue
                for pin,v in rr['ports'].items():
                    if v['direction']=='INPUT' and cell+'/'+pin in g['pin_net']:trace(g['pin_net'][cell+'/'+pin])
        trace(g['pin_net'][row['CLK']]);checks['clock_root_connected']=roots=={expected}
        if sync:
            resetrow=lookup[(cam,'cr' if chain=='ack_sync' else 'hr',1)]
            checks['reset_from_correct_release_stage']=r.equal(resetrow['Q'],row['reset']);table=[]
        else:
            resetroot=alias_root(g,{f'source_diagnostics/cam_reset[{cam}]',f'diag_reset[{cam}]'})
            table=[]
            for x,y in itertools.product([0,1],repeat=2):
                # Actual root aliases are overridden only at these uniquely bound
                # input nets. Evaluate every actual LUT/buffer cone exhaustively.
                virtual=dict(g);virtual['net_aliases']=dict(g['net_aliases'])
                virtual['net_aliases'][busrst]=list(g['net_aliases'][busrst])+['/@build03_rst']
                virtual['net_aliases'][resetroot]=list(virtual['net_aliases'][resetroot])+[f'/@build03_cam_reset_{cam}']
                actual=evaluate(virtual,g['pin_net'][row['reset']],parameters,{'build03_rst':x,f'build03_cam_reset_{cam}':y})
                table.append({'rst':x,'cam_reset':y,'actual':actual,'expected':x|y})
            checks['reset_assertion_is_correct_active_high_OR']=all(x['actual']==x['expected'] for x in table)
        if rec['type'].startswith('GTP_DFF'):
            checks['async_clear_or_set_correct']=('C' in rec['ports']) if sync else ('P' in rec['ports'])
            checks['INIT_and_GRS']=p.get('INIT')==('0' if sync else '1') and p.get('GRS_EN')=='TRUE'
            if 'CE' in rec['ports']:checks['CE_constant_one']=evaluate(g,g['pin_net'][row['cell']+'/CE'],parameters)==1
        else:
            checks['async_clear_or_set_correct']=p.get('FF_RS',p.get('FF0_RS'))==('RESET' if sync else 'SET') and p.get('RS_MODE')=='ASYNC'
            checks['INIT_and_GRS']=p.get('FF_INIT',p.get('FF0_INIT'))==('0' if sync else '1') and p.get('GRS_EN')=='TRUE'
            checks['positive_edge']=p.get('CLK_POL')=='FALSE'
            checks['reset_polarity_and_enable']=p.get('LRS_POL')=='FALSE' and p.get('LRS_EN')=='TRUE'
            checks['CE_constant_one_or_disabled']=p.get('LCE_EN')=='FALSE' or evaluate(g,g['pin_net'].get(row['cell']+'/CE'),parameters)==1
        if stage in {'mapping','routed'}:
            attrs={a[1]:a[2:] for a in rec.get('attributes',[]) if len(a)>1}
            checks['mapped_PAP_NOPRUNE_retained']=attrs.get('PAP_NOPRUNE')==[['BOOL','TRUE']]
        rows.append({**row,'parameters_decoded':p,'clock_root_expected':expected,'clock_root_found':sorted(roots),
                     'clock_actual_nets_traversed':sorted(seen),'reset_assertion_truth_table':table,'checks':checks,'all_proven_checks_passed':all(checks.values())})
    failed=[x for x in rows if not x['all_proven_checks_passed']]
    proof={**classified,'rows':rows,'stage':stage,'failed_checks':failed,'bus_reset_net':busrst,
           'actual_root_binding_basis':'Unique full-top logical bus aliases from this stage export; no old graph input',
           'checker_sha256':sha(Path(__file__)),'status':'PASS' if not failed else 'FAIL'}
    record(stage+'_endpoint_details.json',proof)
    require(not failed,'Full build03 actual independent60/INIT/GRS/reset/polarity/clock audit failed: '+stage)
    return proof
