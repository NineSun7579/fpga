"""Validate byte witnesses, previous direct joins and sparse graph independently."""
from pathlib import Path
import hashlib, json, re
H = Path(__file__).resolve().parent
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
    result_bytes = (H/'join_result.json').read_bytes()
    r = json.loads(result_bytes)
    raw = Path(r['new_graph_binding']['fulltop_input']).read_bytes()
    assert sha(raw) == r['new_graph_binding']['fulltop_sha256']
    assert r['physical_join_complete'] and r['accepted_connection_count'] == 112
    assert not r['errors'] and not r['unresolved_ports']
    assert r['newly_resolved_join01_missing_count'] == 49
    assert r['IOgate'] is r['IO_gate_passed'] is r['internal_bank_metadata_verified'] is False
    assert r['usedIO_internal_bank_objects_verified'] is False
    for p, digest in r['inputs'].items(): assert sha(Path(p).read_bytes()) == digest, p
    count = 0
    def witnesses(node):
        nonlocal count
        if isinstance(node, dict):
            if 'raw_adif' in node:
                data = raw[node['byte_start']:node['byte_end_exclusive']]
                assert data == node['raw_adif'].encode('ascii') and sha(data) == node['sha256']
                count += 1
            for value in node.values(): witnesses(value)
        elif isinstance(node, list):
            for value in node: witnesses(value)
    witnesses(r)
    previous = json.loads((H.parent/'diagnostic_io_bank_join01/join_result.json').read_bytes())
    prior = {row['port']: row for row in previous['rows']}
    candidates = json.loads((H.parent/'diagnostic_io_bank_join01/site_reverse_candidates.json').read_bytes())
    assert candidates['dump_sha256'] == sha(raw)
    reverse = {row['port']: row for row in candidates['rows']}
    graph = json.loads((H/'connection_graph.json').read_bytes())
    assert graph['fulltop_sha256'] == sha(raw) and len(graph['net_aliases']) == 112
    assert len({row['primitive']['instance'] for row in r['rows']}) == 112
    assert len({row['actual_PLACE']['site'] for row in r['rows']}) == 112
    direct = 0
    for row in r['rows']:
        assert row['accepted']
        inst = row['primitive']['instance']; pad = row['primitive']['pad_pin']
        assert row['net_endpoints'] == [[inst, pad], ['', row['port']]] or sorted(row['net_endpoints']) == sorted([[inst, pad], ['', row['port']]])
        assert row['actual_PLACE']['site'] == row['package_site']
        # Re-check exact INSTREF from raw INSTANCE and INSTANNOTATE independently.
        for ev, keyword in [(row['primitive']['instance_evidence'], 'INSTANCE'),
                            (row['actual_PLACE']['evidence'], 'INSTREF')]:
            m = re.search(r'\('+keyword+r'\s+(\S+)\s', ev['raw_adif'])
            assert m and m[1].lstrip('\\') == inst
        cn = row['connect_evidence']['raw_adif']
        assert len(re.findall(r'\(PORTREF\s', cn)) == 2
        assert row['top_port']['locs'] == [row['loc']] or (row['port'] == 'sfp_tx_disable' and row['top_port']['locs'] == [])
        if prior[row['port']]['primitive_places']:
            direct += 1
            assert any(p['instance'] == inst and '_'.join(p['actual_PLACE']) == row['package_site']
                       for p in prior[row['port']]['primitive_places'])
        rev = reverse[row['port']]
        assert rev['site'] == row['package_site'] and rev['loc'] == row['loc']
        assert inst in {p['instance'] for p in rev['site_reverse_candidates']}
        assert graph['net_aliases'][row['port']]['actual_endpoints'] == row['net_endpoints']
    assert direct == 63
    assert len(r['differential_pairs']) == 3 and all(p['accepted'] for p in r['differential_pairs'])
    output = {'status': 'PASS', 'script_sha256': sha(Path(__file__).read_bytes()),
              'join_result_sha256': sha(result_bytes), 'target_sha256': sha(raw),
              'verified_raw_adif_witnesses': count, 'all_input_hashes_reverified': True,
              'prior_63_direct_joins_exactly_preserved': direct,
              'site_reverse_candidates_corroborated_after_actual_connectivity': 112,
              'connection_rows': 112, 'new_missing_rows_resolved': 49,
              'unique_primitive_pad_instances': 112, 'unique_actual_IO_sites': 112,
              'differential_pair_contracts': 3, 'IO_gate_passed': False}
    (H/'validation.json').write_text(json.dumps(output, indent=2), encoding='ascii')
    print(json.dumps(output, indent=2))
if __name__ == '__main__': main()
