"""Adversarial contract tests against real resolved graphs; no PDS."""
from pathlib import Path
import copy,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'runtime'))
from contract import load,validate_mapping,validate_records,SOURCE
from graph_adapter import strict_keepbuf,Resolver
from clock_audit import audit
def main():
    m=load(HERE/'analysis/manifest.json');g=load(HERE/'analysis/graph.json');pairs=validate_mapping(m,g)
    results=[]
    def reject(name,fn):
        try:fn()
        except (RuntimeError,AssertionError,KeyError,ValueError,FileNotFoundError) as e:results.append({'case':name,'rejected':True,'reason':str(e)[:600]})
        else:raise AssertionError('Counterexample accepted: '+name)
    bad=copy.deepcopy(m);bad['resolved'].pop();reject('wrong_logical_count',lambda:validate_mapping(bad,g))
    bad=copy.deepcopy(m);rr=[r for r in bad['resolved'] if r['mapping']['kind']=='register' and r['camera']==0]
    a=next(r for r in rr if r['logical_bit']==240);b=next(r for r in rr if r['logical_bit']==0);a['mapping'],b['mapping']=b['mapping'],a['mapping']
    reject('same_count_wrong_alias_membership',lambda:validate_mapping(bad,g))
    bad=copy.deepcopy(m);bad['errors']=[{'actual':'resolve failed'}];reject('resolve_errors_nonzero',lambda:validate_mapping(bad,g))
    rows=[{'start':p['CLK'],'end':p['D'],'corner':c,'exception':'MaxDelay Path 15.238','slack':0.1} for p in pairs for c in ['Slow','Fast']]
    assert validate_records(rows,pairs)
    from report_records import records
    fixture=HERE/'regression_fixtures/SYNTHETIC_not_STA.rtr';fixture.parent.mkdir(exist_ok=True)
    fixture.write_text(''.join('Startpoint: '+r['start']+'\nEndpoint: '+r['end']+'\nPath Type: max '+r['corner'].lower()+' corner\nTiming Exception: '+r['exception']+'\nSlack (MET) 0.100\n' for r in rows),encoding='ascii')
    scored=list(records(fixture));assert validate_records(scored,pairs)
    reject('parsed_missing_corner',lambda:validate_records(scored[:-1],pairs))
    reject('wrong_physical_target_count',lambda:validate_records(rows,pairs[:-1]))
    reject('missing_corner',lambda:validate_records(rows[:-1],pairs))
    reject('duplicate_same_count',lambda:validate_records(rows[:-1]+[rows[0]],pairs))
    bad=copy.deepcopy(rows);bad[0]['exception']='MaxDelay Path 16.000';reject('wrong_report_budget',lambda:validate_records(bad,pairs))
    bad=copy.deepcopy(rows);bad[0]['end']=rows[2]['end'];reject('cartesian_cross_pair',lambda:validate_records(bad,pairs))
    raw=(HERE/'constraints/clock.fdc').read_bytes();proof=load(HERE/'coverageproof.json')
    reject('wrong_clock_budget',lambda:audit(raw.replace(b'15.238',b'15.239'),proof))
    reject('extra_same_domain_falsepath',lambda:audit(raw+b'set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {ddrphy_sysclk}]\n',proof))
    cg=load(SOURCE/'evidence/runtime/compile/analysis/graph.json');sample=next(copy.deepcopy(r) for r in cg['primitives'].values() if r['type']=='bmsKEEPBUF_Cell_1')
    assert strict_keepbuf(sample)
    for name,fn in [('unknown_primitive',lambda r:r.update(type='bmsKEEPBUF_Cell_999')),('wrong_width',lambda r:r.update(default_parameters=[['PARAMETER','WIDTH',['DATATYPE','INTEGER'],['INTEGER','2']]])),('extra_control',lambda r:r['ports'].update(E={'direction':'INPUT','clock':False})),('clock_state',lambda r:r['ports']['I[0]'].update(clock=True))]:
        bad=copy.deepcopy(sample);fn(bad);reject(name,lambda bad=bad:strict_keepbuf(bad))
    # Real dangling clock branches are accepted only when the output has no net
    # in either index and the exact proven identity schema remains intact.
    terminals=[]
    for cam in range(4):terminals.extend(x for x in Resolver(cg).clock_leaves(cam)['transparent'] if x.get('disposition')=='identity_terminal_no_output_net_no_storage')
    assert terminals
    bad=copy.deepcopy(cg);cell=terminals[0]['cell'];inputpin=cell+'/I[0]';out=cell+'/Z[0]';net=bad['pin_net'][inputpin];bad['netpins'][net].append(out)
    reject('inconsistent_dangling_output_index',lambda:Resolver(bad).clock_leaves(0))
    fake={'primitives':{'bad':{'type':'UNKNOWN_CLOCK_GATE','ports':{'I':{'direction':'INPUT','clock':False}}}},'pin_net':{'bad/I':'root'},'netpins':{'root':['bad/I']},'net_aliases':{'root':['cmos1_pclk']}}
    reject('unknown_clock_sink',lambda:Resolver(fake).clock_leaves(0))
    fake['primitives']['bad']={'type':'GTP_DFF_UNKNOWN','ports':{'CLK':{'direction':'INPUT','clock':True}}};fake['pin_net']={'bad/CLK':'root'};fake['netpins']={'root':['bad/CLK']}
    reject('unknown_storage_prefix',lambda:Resolver(fake).clock_leaves(0))
    from gates import check
    reject('route_disabled_without_main_evidence',check)
    (HERE/'offline_regression.json').write_text(json.dumps({'passed':True,'rejections':results,'synthetic_scored_fixture_only':True,'real_STA_claimed':False,'strict_identity_dangling_branches':len(terminals)},indent=2)+'\n',encoding='ascii')
    print('PASS: %d adversarial rejections; %d real strict-identity dangling branches'%(len(results),len(terminals)))
if __name__=='__main__':main()
