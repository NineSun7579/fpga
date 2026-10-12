"""Bounded missing-reset and clock checks; diagnostic evidence only, no waiver."""
import json
import sys
import traceback
from pathlib import Path
import preflight
import physical_flow as flow

def main():
    base=preflight.HERE;root=base/'route_attempt_03'
    flow.HERE=root;flow.EVIDENCE=root/'evidence';flow.PROJECT=root/'project.pds'
    from targeted_reports import query
    route=root/'place_route/v7_sdt_top_pnr.adf'
    preflight.require(preflight.sha(route)==preflight.load(flow.EVIDENCE/'pnr_artifact.json')['sha256'],'Route drift')
    proof=preflight.load(flow.EVIDENCE/'coverageproof_physical_receivers.json')
    results={}
    targets=[('missing_reset_one',['source_diagnostics/cameras[0].source/cr[0]/opit_0/RS']),
             ('reset_clock_mpw',[g['physical'].rsplit('/',1)[0]+'/CLK' for g in proof['reset_bindings']])]
    for label,ends in targets:
        try:
            report,rows=query(route,label,ends=ends,max_path=256,nworst=10)
            results[label]={'scored_records':len(rows),'records':rows,'report':str(report),'report_sha256':preflight.sha(report)}
        except Exception as exc:
            results[label]={'query_not_proven':str(exc),'traceback':traceback.format_exc(),
                'actual_report':str(flow.EVIDENCE/label/'report_timing/v7_sdt_top.rtr')}
        flow.record('reset_mpw_diagnostic_result.json',{'route_sha256':preflight.sha(route),'results':results,
            'FDC_changed':False,'full_signoff':False,'bit_allowed':False})
    sta=preflight.load(flow.EVIDENCE/'evidence/final_sta_summary.json')
    mailbox=preflight.load(flow.EVIDENCE/'evidence/mailbox_routed_audit.json')
    flow.record('actual_result.json',{'phase':'ACTUAL_STA_AND_MAILBOX_PASS_RESET_INTERNAL_SIGNOFF_UNPROVEN',
        'route_sha256':preflight.sha(route),'full_signoff':False,'bit_allowed':False,'remote_or_program':False,
        'ten_groups':[{'section':g['section'],'corner':g['corner'],'failing_endpoints':g['sum_failing_endpoints'],
                       'worst_slack_ns':min(r['worst_slack_ns'] for r in g['rows'])} for g in sta['all_corner_summaries']],
        'mailbox':mailbox['details'],'io112':preflight.load(flow.EVIDENCE/'evidence/io_audit.json'),
        'reset_sync':preflight.load(flow.EVIDENCE/'remaining_actual_result.json'),'reset_mpw_diagnostics':results,
        'required_remaining':['Reset32 lane Recovery/Removal/MPW actual evidence','8 packed internal sync timing checks','Independent review of bank-label report inconsistency']})
    flow.status('ATTEMPT03_ACTUAL_REPORTS_COMPLETE_RESET_INTERNAL_PROOF_UNMET_NO_BIT')

if __name__=='__main__':main()
