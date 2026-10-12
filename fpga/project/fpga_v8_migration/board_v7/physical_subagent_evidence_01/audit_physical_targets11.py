"""当前routed真实目标：单对zero-ignored后四相机完整1320双角，流式验收。"""
from pathlib import Path
import json,re
import generate_exact11 as gen
import continue_fixed as cf
from stream_timing11 import records,validate_logs
import physical_targets11
def tcl_list(values):return '{'+' '.join('{'+v+'}' for v in sorted(set(values)))+'}'
def query(out,route,name,pairs,ends,max_path):
    dest=out/('physical_target_'+name);dest.mkdir()
    starts=[a for a,b in pairs];ends=ends or [b for a,b in pairs]
    cmd='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -report_exception TRUE -input_pins TRUE -nworst 2 -max_path '+str(max_path)
    if starts:cmd+=' -from '+tcl_list(starts)
    cmd+=' -to '+tcl_list(ends)
    script=dest/'export.tcl';script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+cmd+'\n',encoding='ascii')
    label='physical_target_'+name;cf.run(label,[str(cf.PDS),'-file',str(script),'-work_dir',str(dest),'-project_name','exact11_'+name],dest)
    logproof=validate_logs([out/(label+'.log'),dest/'run.log',dest/'report_timing/run.log'])
    gen.write_json(out/(label+'_logproof.json'),logproof)
    assert logproof['passed'],'物理目标被工具忽略，保留真实 Timing-4006/STA-3016/unknown 日志，禁止放行'
    expected=set(tuple(p) for p in pairs);expected_ends=set(ends)
    details={corner:{'covered':set(),'budget_covered':set(),'missing':[],'unexpected':set(),'worst_slack':None,'records':0,'budget_records':0,
                     'bad_budget':[],'checks':{'Recovery':set(),'Removal':set(),'Setup':set(),'Hold':set()}} for corner in ['Slow','Fast']}
    unknown=[];negative=[];bad_targets=[]
    report=dest/'report_timing/v7_sdt_top.rtr'
    for row in records(report):
        pair=(row['start'],row['end']);corner=row['corner']
        if (expected and pair not in expected) or row['end'] not in expected_ends:
            if len(bad_targets)<100:bad_targets.append(row)
        if corner not in details:
            if len(unknown)<100:unknown.append(row)
            continue
        d=details[corner];d['records']+=1
        if row['slack']<0:negative.append(row)
        d['worst_slack']=row['slack'] if d['worst_slack'] is None else min(d['worst_slack'],row['slack'])
        if expected:
            d['covered'].add(pair)
            if pair not in expected:d['unexpected'].add(pair)
        if row['check']:d['checks'][row['check']].add(row['end'])
        if row['exception'] and 'MaxDelay Path' in row['exception']:
            d['budget_records']+=1
            good=bool(re.search(r'MaxDelay Path\s+15\.238ns\s+-datapath_only',row['exception']))
            if not good:d['bad_budget'].append(row)
            elif pair in expected:d['budget_covered'].add(pair)
    for corner,d in details.items():
        d['missing']=sorted(expected-d['covered']) if expected else []
        d['covered']=len(expected&d['covered']) if expected else len(expected_ends&set().union(*d['checks'].values()))
        d['unexpected']=sorted(d['unexpected'])
        d['budget_missing']=sorted(expected-d['budget_covered'])
        d['budget_covered']=len(d['budget_covered'])
        d['checks']={check:{'covered':len(values&expected_ends),'missing':sorted(expected_ends-values)} for check,values in d['checks'].items()}
    result={'name':name,'target_filter_passed':not bad_targets and not unknown,'logs':logproof,'details':details,
            'bad_targets':bad_targets,'unknown_corner':unknown,'negative':negative,'negative_count':len(negative),
            'report_path':str(report),'report_bytes':report.stat().st_size,'report_sha256':cf.sha(report)}
    gen.write_json(out/(label+'_audit.json'),result)
    assert result['target_filter_passed'],'报告包含目标外路径或未知corner，筛选尚未实证有效'
    return result
def main(out,route):
    cf.idle();h=cf.sha(route);proof=physical_targets11.prepare(out,route)
    assert proof['route_sha256']==h
    physical=[tuple(r['physical']) for r in proof['pairs']]
    assert len(set(physical))==1320 and len(physical)==1320
    allresults=[]
    # 真实单对probe有预算/双角且无任何ignored，才可以继续完整对象集合。
    probe=query(out,route,'single_pair',physical[:1],[],8)
    assert all(d['covered']==1 and not d['missing'] and not d['unexpected'] and not d['bad_budget'] and not d['budget_missing'] and d['budget_covered']==1 for d in probe['details'].values()),'singlepair双角预算/覆盖未成立'
    for camera in range(4):
        selected=[tuple(r['physical']) for r in proof['pairs'] if r['logical'][0].startswith(f'source_diagnostics/cameras[{camera}].source/')]
        assert len(selected)==330
        result=query(out,route,f'mailbox_camera{camera}',selected,[],1400);allresults.append(result)
        assert cf.sha(route)==h
    details={};mailboxpass=True
    for corner in ['Slow','Fast']:
        rows=[r['details'][corner] for r in allresults]
        d={'covered':sum(r['covered'] for r in rows),'missing':[p for r in rows for p in r['missing']],
           'unexpected':[p for r in rows for p in r['unexpected']],
           'worst_slack':min(r['worst_slack'] for r in rows if r['worst_slack'] is not None),
           'records':sum(r['records'] for r in rows),'budget_records':sum(r['budget_records'] for r in rows),
           'budget_covered':sum(r['budget_covered'] for r in rows),'budget_missing':[p for r in rows for p in r['budget_missing']],
           'bad_budget':[p for r in rows for p in r['bad_budget']]}
        details[corner]=d
        mailboxpass&=d['covered']==1320 and not d['missing'] and not d['unexpected'] and not d['bad_budget'] and not d['budget_missing'] and d['budget_covered']==1320 and d['worst_slack']>=0
    gen.write_json(out/'evidence/mailbox_routed_audit.json',{'passed':bool(mailboxpass),'physical_targets':True,'details':details,'camera_report_receipts':[str(out/('physical_target_mailbox_camera'+str(i)+'_audit.json')) for i in range(4)]})
    resetpass=False
    if proof['reset_semantic_binding_passed']:
        ends=[r['physical'] for r in proof['reset_bindings']]
        reset=query(out,route,'reset',[],ends,max(128,len(ends)*8))
        resetpass=all(not d['checks'][check]['missing'] and d['worst_slack'] is not None and d['worst_slack']>=0 for d in reset['details'].values() for check in ['Recovery','Removal'])
        gen.write_json(out/'evidence/reset_routed_audit.json',{'passed':resetpass,'physical_targets':True,'details':reset['details'],'negative':reset['negative'],'semantic_bindings':proof['reset_bindings']})
    else:
        gen.write_json(out/'evidence/reset_routed_audit.json',{'passed':False,'binding_errors':proof['reset_binding_errors'],'no_query_for_unproved_reset':True})
    syncpairs=[tuple(r['physical']) for r in proof['sync_bindings']]
    sync=query(out,route,'sync_later',syncpairs,[],max(128,len(syncpairs)*8))
    syncpass=proof['sync_binding_passed'] and not proof['sync_packed_internal'] and all(d['covered']==len(syncpairs) and not d['missing'] and not d['unexpected'] and d['worst_slack'] is not None and d['worst_slack']>=0 for d in sync['details'].values())
    gen.write_json(out/'evidence/sync_later_routed_audit.json',{'passed':syncpass,'physical_targets':True,'details':sync['details'],'negative':sync['negative'],
        'packed_internal_requires_timing_evidence':proof['sync_packed_internal'],'binding_errors':proof['sync_binding_errors']})
    assert cf.sha(route)==h
    result={'mailbox':bool(mailboxpass),'reset':bool(resetpass),'sync_later':bool(syncpass),'singlepair_zero_ignored':True,'physical_target_filter':True,'route_sha256':h}
    gen.write_json(out/'physical_target_acceptance.json',result)
    return result
