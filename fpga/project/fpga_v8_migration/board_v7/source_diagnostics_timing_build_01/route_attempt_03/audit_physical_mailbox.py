"""Exhaustive actual routed receivers and bound mailbox reports; no bit/signoff."""
from pathlib import Path
import traceback
from preflight import HERE, load, sha, require
from physical_flow import EVIDENCE, wait_idle, protected, record, status
from targeted_reports import query, audit_targets

def main():
    wait_idle(); protected()
    route = HERE / 'place_route/v7_sdt_top_pnr.adf'
    require(sha(route) == load(EVIDENCE / 'pnr_artifact.json')['sha256'], 'Route drift')
    g = load(EVIDENCE / 'routed/analysis/graph.json')
    proof = load(EVIDENCE / 'coverageproof_final_pnr_synthesis.json')
    require(load(EVIDENCE / 'final_graph_constraint_comparison.json')['same_generated_bytes'], 'Final graph constraints differ')
    pr, pn, np = g['primitives'], g['pin_net'], g['netpins']
    fdc = (HERE / 'constraints_candidate/clock.fdc').read_bytes().splitlines()
    def bound(logical):
        cell, port = logical.rsplit('/', 1)
        pins = [k+'/'+port for k, r in pr.items() if k.startswith(cell+'/') and port in r['ports'] and k+'/'+port in pn]
        require(len(pins) == 1, 'Nonunique mailbox physical binding: '+logical)
        return pins[0]
    pairs, cameras = [], []
    for cam in proof['cameras']:
        i = cam['camera']; roots = {n for n, a in g['net_aliases'].items() if f'cmos{i+1}_pclk' in a or f'/@cmos{i+1}_pclk' in a}
        require(len(roots) == 1, 'Actual physical root nonunique')
        queue = list(roots); seen = set(); leaves = set(); edges = {}; unknown = []
        while queue:
            net = queue.pop()
            if net in seen: continue
            seen.add(net)
            for pin in np[net]:
                cell, port = pin.rsplit('/',1); r = pr[cell]; typ = r['type']; linked = None
                if typ == 'gopIBUF':
                    linked = ['I', 'O'] if port in ['I','O'] else []
                elif typ.startswith('gopIOL_Cell_') and cell.startswith(f'cmos{i+1}_pclk_ibuf/'):
                    require(any(a[1:] == ['PAP_IO_NONE', ['STRING','TRUE']] for a in r['attributes']), 'Clock IOL is not combinational bypass')
                    linked = ['DI','DI_TO_CLK'] if port in ['DI','DI_TO_CLK'] else []
                elif typ in ['gopCLKBUFG','gopHCKB','gopCLKROUTE']:
                    expected = {'gopCLKBUFG': {'CLK','CLKOUT'}, 'gopHCKB': {'CLKIN','CLKOUT'}, 'gopCLKROUTE': {'M','CR'}}[typ]
                    require(set(r['ports']) == expected and not r['parameters'], 'Unknown controlled clock routing configuration')
                    linked = sorted(expected)
                if linked is not None:
                    edges[cell] = {'type': typ, 'ports': linked, 'parameters': r['parameters'], 'default_parameters': r['default_parameters']}
                    queue.extend(pn[cell+'/'+p] for p in linked if cell+'/'+p in pn)
                elif r['ports'][port]['direction'] == 'INPUT':
                    if (typ.startswith('gopQ') and port == 'CLK') or (typ.startswith('gopDRM') and port in ['CLKA','CLKB']):
                        leaves.add(pin)
                    else: unknown.append({'pin':pin,'type':typ})
        require(leaves and not unknown, 'Unknown actual camera clock receiver')
        camera_pairs = []
        for a,b in cam['physical_pairs']:
            launch,capture = bound(a),bound(b); q = launch.rsplit('/',1)[0]+'/Q'
            require(launch in leaves, 'Mailbox absent from exhaustive routed clock graph')
            path = []; direct = pn[q] == pn[capture]
            if not direct:
                candidates = []
                for pin in np[pn[q]]:
                    cell,port = pin.rsplit('/',1); r = pr[cell]
                    if port == 'M' and r['type'] == 'gopCLKROUTE' and pn.get(cell+'/CR') == pn[capture]: candidates.append(cell)
                require(len(candidates) == 1, 'Mailbox Q-D not direct or unique actual routing connection')
                path = candidates
                report, rows = query(route, 'mailbox_route_bridge_probe', pairs=[(launch,capture)], max_path=8)
                require({r['corner'] for r in rows} == {'Slow','Fast'} and all(r['exception'] and 'MaxDelay Path 15.238' in r['exception'] for r in rows), 'Routing bridge timing/budget not proven')
            row = {'logical':[a,b], 'physical':[launch,capture], 'direct_Q_to_D':direct, 'routing_bridge':path}
            camera_pairs.append(row);pairs.append(row)
        mailbox = {r['physical'][0] for r in camera_pairs}; comp = leaves-mailbox; provenance = []
        for pin in leaves:
            cell,port = pin.rsplit('/',1); entries = [dict(e[1:]) for e in pr[cell].get('cdb_entries',[])]
            matches = []
            for entry in entries:
                if Path(entry.get('FILENAME','').strip('"')).resolve() != (HERE/'constraints_candidate/clock.fdc').resolve(): continue
                number = int(entry['LINENUM']); line = fdc[number-1]
                if pin in comp and line.startswith(b'set_false_path -from [get_pins') and b'-to [get_clocks {ddrphy_sysclk}]' in line:
                    matches.append(entry)
                if pin in mailbox and line.startswith(b'set_max_delay -datapath_only 15.238 -from [get_pins'):
                    matches.append(entry)
            require(matches, 'Actual physical receiver lacks correct inherited exception: '+pin)
            provenance.append({'pin':pin,'classification':'mailbox' if pin in mailbox else 'complement','cdb_entries':matches})
        require(len(mailbox)==330 and mailbox.isdisjoint(comp) and mailbox|comp == leaves, 'Routed partition not exhaustive')
        cameras.append({'camera':i,'roots':sorted(roots),'nets':sorted(seen),'transparent':edges,'leaves':sorted(leaves),
                        'mailbox_launches':sorted(mailbox),'complement':sorted(comp),'unknown':unknown,'provenance':provenance})
    result = {'passed':True,'physical_pair_count':len(pairs),'pairs':pairs,'cameras':cameras,'errors':[],
              'route_sha256':sha(route),'method':'exhaustive physical root traversal and every receiver CDB line, no synthesis leaf deletion',
              'reset_sync_signoff':False}
    require(len(pairs)==1320,'Physical pair count changed')
    record('coverageproof_physical_receivers.json',result)
    gates = audit_targets(route,result,[],[],mailbox_only=True)
    record('actual_mailbox_completion.json',{'passed':True,'gates':gates,'route_sha256':sha(route),'full_signoff':False})
    status('MAILBOX1320_ACTUAL_BOTH_CORNERS_PASS_RESET_SYNC_PENDING')

if __name__ == '__main__':
    try: main()
    except BaseException:
        (EVIDENCE/'physical_mailbox_failure.txt').write_text(traceback.format_exc(),encoding='utf8')
        status('PHYSICAL_MAILBOX_AUDIT_FAILED')
        raise
