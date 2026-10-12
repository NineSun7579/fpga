"""Export complete scored MPW tables, with exceptions disabled and no data endpoints."""
import preflight
import physical_flow as flow

def main():
    root=preflight.HERE/'route_attempt_03';flow.HERE=root;flow.EVIDENCE=root/'evidence';flow.PROJECT=root/'project.pds'
    from targeted_reports import query
    proof=preflight.load(flow.EVIDENCE/'coverageproof_physical_receivers.json')
    clocks=sorted({r['physical'].rsplit('/',1)[0]+'/CLK' for r in proof['reset_bindings']})
    route=root/'place_route/v7_sdt_top_pnr.adf'
    preflight.require(preflight.sha(route)==proof['route_sha256'],'Route drift')
    query(route,'reset_clock_mpw_complete',ends=clocks,max_path=200000,nworst=1,mpw_table_only=True)
    import audit_attempt03_mpw_rows as audit
    audit.main('reset_clock_mpw_complete')

if __name__=='__main__':main()
