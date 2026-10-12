"""One actual bound physical pair, diagnostic only; no coverage/signoff inference."""
from preflight import HERE, load, sha, require
from physical_flow import EVIDENCE, wait_idle, protected, record, status
from targeted_reports import query

def main():
    wait_idle(); protected()
    route = HERE / 'place_route/v7_sdt_top_pnr.adf'
    require(sha(route) == load(EVIDENCE / 'pnr_artifact.json')['sha256'], 'Route drift')
    coverage = load(EVIDENCE / 'coverageproof_routed.json')
    row = coverage['pairs'][0]
    require(row['direct_Q_to_D'] is True, 'No proved physical pair')
    pair = tuple(row['physical'])
    report, rows = query(route, 'diagnostic_single_physical_pair', pairs=[pair], max_path=8)
    require({r['corner'] for r in rows} == {'Slow', 'Fast'}, 'Both corners absent')
    require(all((r['start'], r['end']) == pair and r['exception'] and
                'MaxDelay Path 15.238' in r['exception'] for r in rows), 'Exact filter/budget mismatch')
    record('diagnostic_single_pair_result.json', {'passed': True, 'physical_pair': pair,
           'logical_pair': row['logical'], 'route_sha256': sha(route), 'rows': rows,
           'report_sha256': sha(report), 'full_coverage_or_signoff_claimed': False})
    status('SINGLE_PHYSICAL_FILTER_PROVEN_FULL_COVERAGE_STILL_BLOCKED')

if __name__ == '__main__':
    main()
