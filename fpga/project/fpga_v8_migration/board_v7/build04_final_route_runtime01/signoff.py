"""Offline signoff consumer for future evidence; cannot generate a bitstream.

Independent semantic reviewers still supply mapping/IO/HSST/motion/reload proofs.
Every scored mailbox row is parsed from actual native reports, never receipts.
"""
from pathlib import Path
import argparse,json,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'runtime'))
from contract import load,sha,require,validate_mapping,validate_records,BOARD
from report_records import records
from gates import check,bound_files
def audit(bundle):
    check();b=load(bundle);art=b['artifacts'];bound_files(list(art.values()))
    route=Path(art['route']['path']);rh=sha(route)
    require(b['route_sha256']==rh and b.get('independent_reviewer'),'Unreviewed/wrong route')
    graph=load(art['routed_graph']['path']);manifest=load(art['routed_manifest']['path'])
    require(b.get('routed_manifest_rederived_from_raw') is True and b.get('routed_raw_sha256')==art['routed_dump']['sha256'],'Fresh routed derivation provenance missing')
    pairs=validate_mapping(manifest,graph,routed=True)
    for p in pairs:
        require(p['Q'] in graph['pin_net'] and p['CLK'] in graph['pin_net'],'Routed target missing')
    rows=[]
    for name in b['mailbox_reports']:rows.extend(records(art[name]['path']))
    validate_records(rows,pairs)
    global10=load(art['global_summary']['path'])['all_corner_summaries'];kinds={'Setup','Hold','Recovery','Removal','Minimum Pulse Width'}
    require(len(global10)==10 and {(x['section'],x['corner']) for x in global10}=={(k,c) for k in kinds for c in ['Slow','Fast']},'Global ten-group coverage missing')
    for group in global10:
        require(group['rows'] and group['sum_failing_endpoints']==0,'Global failures/empty group')
        require(all(r['worst_slack_ns']>=0 and r['total_negative_slack_ns']==0 and r['total_endpoints']>0 for r in group['rows']),'Global slack/endpoint failure')
    # Exact routed reset/sync target identities must come from independent60
    # semantics, with every group bound to this same routed ADF.
    targets=load(art['routed_targets60']['path'])
    require(targets['route_sha256']==rh and len(targets['reset'])==32 and len(targets['later_sync'])==16,'Wrong routed60 target binding')
    reset={r['reset'] for r in targets['reset']};clocks={r['CLK'] for r in targets['reset']};sync={tuple(r) for r in targets['later_sync']}
    require(len(reset)==len(clocks)==32 and len(sync)==16,'Nonindependent targeted pins')
    for name,ends,checks,pairset in [('reset_report',reset,{'Recovery','Removal'},None),('reset_mpw_report',clocks,{'Minimum Pulse Width'},None),('later_sync_report',None,{'Setup','Hold'},sync)]:
        rr=list(records(art[name]['path']));require(rr,'Empty targeted report')
        for corner in ['Slow','Fast']:
            for kind in checks:
                selected=[r for r in rr if r['corner']==corner and r['check']==kind]
                actual={(r['start'],r['end']) for r in selected} if pairset else {r['end'] for r in selected}
                require(actual==(pairset if pairset else ends) and all(r['slack']>=0 for r in selected),'Targeted exact coverage/slack failure '+name)
    for name in ['routed60_semantics','IO112bank','HSST','motion32','timing_reload']:
        receipt=load(art[name]['path'])
        require(receipt.get('route_sha256')==rh and receipt.get('independent') is True and receipt.get('reviewer'),'Unbound physical proof '+name)
        require(receipt.get('complete') is True and receipt.get('raw_files') and receipt.get('coverage'),'Unclosed physical proof '+name)
        bound_files(receipt['raw_files'])
        if name=='HSST':
            baseline=load(BOARD/'source_diagnostics_timing_build_03/runtime/baseline_data/hsst_phy.json')['actual']
            require(receipt.get('actual')==baseline,'HSST exact sites/dedicated connections differ')
        elif name=='motion32':
            memories=receipt['memories'];require(len(memories)==len({x['cell'] for x in memories})==32,'Motion exact32 memory identity')
            require(all(x.get('primitive')=='DRM36K' and x.get('read_mode')=='read_first' and x.get('geometry_verified') is True and x.get('data_address_connectivity_verified') is True and x.get('raw_binding') for x in memories),'Motion geometry/read_first/connectivity gap')
        elif name=='IO112bank':
            ports=receipt['ports'];require(len(ports)==len({x['port'] for x in ports})==112 and len(receipt['differential_pairs'])==3,'IO exact112/3 coverage')
            require(all(all(x.get(k) is not None for k in ['internal_bank','pin','VCCIO','IOSTANDARD','VREF','termination','drive']) for x in ports),'Incomplete IO bank/electrical evidence')
        elif name=='routed60_semantics':
            endpoints=receipt['endpoint_bindings'];require(len(endpoints)==len({x['physical_cell'] for x in endpoints})==len({x['site'] for x in endpoints})==60,'Routed physical60 independence')
            require({x['logical'] for x in endpoints}=={x['target'] for x in load(BOARD/'production60_target_prepare01/site_candidate_plan.json')['rows']},'Routed logical60 exact set mismatch')
        elif name=='timing_reload':
            proof=load(HERE/'coverageproof.json')
            require(receipt.get('replacement_clock_sha256')==sha(HERE/'constraints/clock.fdc') and receipt.get('retained_clock_pairs')==proof['retained_clock_pairs'],'Routed timing reload revision/set mismatch')
            require(receipt.get('measured') is True and receipt.get('old_group_absent') is True and receipt.get('no_remap') is True,'Unmeasured CDB replacement/no-remap')
    # Native/shell/raw report parser provenance and ignored-filter exclusion are
    # mandatory independent evidence, never inferred from summary status.
    for name in b['native_logs']:
        raw=Path(art[name]['path']).read_bytes().lower()
        require(not any(x in raw for x in [b'timing-4006',b'sta-3016',b'unsupported',b'ignored',b'unresolved',b'error:',b'fatal']), 'Native report/filter error')
    require(b['native_logs'] and b.get('parser_execution_sha256')==sha(Path(__file__)),'Parser execution provenance missing')
    out={'schema':'deliverySources/v1','candidate_id':HERE.name,'source_candidate_id':'source_diagnostics_timing_build_04','route_sha256':rh,'contract_sha256':sha(HERE/'candidate_specific_expectation_contract.json'),'artifacts':art,'mailbox_expected_pairs':1280,'physical_pair_corners':2560,'accepted':False,'reviewer':None,'board_verified':False,'bit_generated':False,'independent_delivery_acceptance_required':True}
    (HERE/'delivery_sources_NO_BIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='ascii');return out
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('bundle');audit(ap.parse_args().bundle)
