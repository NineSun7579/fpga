"""Read-only exact ADIF port/NET/PORTREF/primitive/PLACE join; no PDS or board access.

Only writes beside this script. Existing parser helpers are imported without running
main or writing bytecode. Target is a flattened TOP, so hierarchy is retained in
exact INSTREF identifiers, never inferred from a substring or site reverse lookup.
"""
from pathlib import Path
import sys, re, json, hashlib, importlib.util, collections
import xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
B = H.parent
E = B/'source_diagnostics_timing_build_01/route_attempt_03/evidence'
TARGET = E/'final_export/routed_dump.txt'
PARSER = E/'routed/analysis/parse_objects.py'
TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+')
BALANCE = re.compile(rb'"(?:[^"\\]|\\.)*"|[()]')
spec = importlib.util.spec_from_file_location('original_parser', PARSER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
child, children, name = helpers.child, helpers.children, helpers.name

def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())
def parse(raw):
    stack = []; result = None
    for match in TOKEN.finditer(raw):
        t = match.group().decode('ascii')
        if t == '(': stack.append([])
        elif t == ')':
            n = stack.pop()
            if stack: stack[-1].append(n)
            else: result = n
        else: stack[-1].append(t)
    assert not stack and result is not None
    return result

def end(raw, start):
    depth = 0
    for m in BALANCE.finditer(raw, start):
        t = m.group()
        if t == b'(': depth += 1
        elif t == b')':
            depth -= 1
            if depth == 0: return m.end()
    raise ValueError(('unbalanced', start))

def evidence(raw, start, stop):
    data = raw[start:stop]
    return {'input': str(TARGET), 'byte_start': start, 'byte_end_exclusive': stop,
            'sha256': sha_bytes(data), 'raw_adif': data.decode('ascii')}

def xml_rows(path):
    return [[d.text or '' for d in row.findall('data')]
            for row in ET.fromstring(path.read_bytes()).findall('row')]

def main():
    assert H.name == 'diagnostic_io_bank_join02', 'write only the new diagnostic directory'
    paths = [TARGET, PARSER, H/'probe.py',
             E/'evidence/place_route_pnr_io_report.xml',
             E/'evidence/place_route_pnr_pinout_report.xml',
             B/'diagnostic_io_bank_join01/join_result.json',
             B/'diagnostic_io_bank_join01/site_reverse_candidates.json']
    bindings = []
    for variant in ['routed', 'actual_final_pnr']:
        base = E/variant
        inputs = [base/'synthesis_export/synthesis_dump.txt', base/'analysis/objects.json',
                  base/'analysis/graph.json', base/'analysis/parse_objects.py']
        paths += inputs
        recorded = json.loads(inputs[1].read_text())['dump_sha256']
        actual = sha(inputs[0])
        bindings.append({'variant': variant, 'fulltop_input': str(inputs[0]),
                         'actual_input_sha256': actual, 'objects_recorded_sha256': recorded,
                         'input_binding_verified': actual == recorded,
                         'alias_graph': str(inputs[2]), 'graph_sha256': sha(inputs[2]),
                         'target_hash_equal': actual == sha(TARGET),
                         'reused_for_acceptance': False,
                         'reason': 'different fulltop input; graph contains no own input hash'})
    before = {str(p): sha(p) for p in dict.fromkeys(paths)}
    raw = TARGET.read_bytes()
    io = xml_rows(paths[3]); pins = xml_rows(paths[4])
    assert len(io) == 112 and len({r[0] for r in io}) == 112
    old = json.loads(paths[5].read_text())
    old_missing = {r['port'] for r in old['errors']}
    assert len(old_missing) == 49
    top_match = re.search(rb'\(CELL v7_sdt_top\s', raw)
    assert top_match and len(re.findall(rb'\(CELL v7_sdt_top\s', raw)) == 1
    top_start = top_match.start(); top_end = end(raw, top_start)
    interface_start = raw.index(b'(INTERFACE', top_start)
    interface_end = end(raw, interface_start)
    interface = parse(raw[interface_start:interface_end])
    top_ports = {}
    for p in children(interface, 'PORT'):
        decl = p[1]; base = name(decl)
        bits = range(int(decl[3]), int(decl[2])+1) if isinstance(decl, list) else [None]
        for bit in bits:
            pn = base if bit is None else f'{base}[{bit}]'
            locs = []
            for a in children(p, 'ATTRIBUTE'):
                if a[1] != 'PAP_IO_LOC': continue
                if len(a) == 3 or (bit is not None and str(bit) in a[3].strip('"').split(',')):
                    locs.append(name(a[2][1]))
            top_ports[pn] = {'direction': child(p, 'DIRECTION')[1], 'locs': locs,
                             'array_declaration': decl, 'bit': bit, 'port_ast': p}
    cont_start = raw.index(b'(CONTENTS', interface_end)
    cont_end = end(raw, cont_start)
    assert cont_end < top_end
    instances = {}
    for m in re.finditer(rb'\(INSTANCE\s', raw[cont_start:cont_end]):
        start = cont_start+m.start(); stop = end(raw, start); n = parse(raw[start:stop])
        ident = name(n[1]); assert ident not in instances
        view = child(n, 'VIEWREF'); ct = child(view, 'CELLREF')
        instances[ident] = {'type': name(ct[1]), 'view': name(view[1]),
                            'node': n, 'range': (start, stop)}
    print('parsed TOP instances', len(instances), flush=True)
    nets = []; top_connections = collections.defaultdict(list)
    pin_connections = collections.defaultdict(list)
    for m in re.finditer(rb'\(NET\s', raw[cont_start:cont_end]):
        start = cont_start+m.start(); stop = end(raw, start); n = parse(raw[start:stop])
        connects = children(n, 'CONNECT')
        raw_connects = list(re.finditer(rb'\(CONNECT\s', raw[start:stop]))
        assert len(connects) == len(raw_connects)
        for c, cm in zip(connects, raw_connects):
            nr = child(c, 'NETREF'); nn = name(nr[1]) if nr else name(n[1])
            eps = [(name(child(p, 'INSTREF')[1]) if child(p, 'INSTREF') else '', name(p[1]))
                   for p in children(c, 'PORTREF')]
            cs = start+cm.start(); ce = end(raw, cs)
            rec = {'net': nn, 'endpoints': eps, 'net_range': (start, stop), 'connect_range': (cs, ce)}
            idx = len(nets); nets.append(rec)
            for ins, pin in eps:
                if ins: pin_connections[(ins, pin)].append(idx)
                else: top_connections[pin].append(idx)
    print('parsed TOP NET/CONNECT records', len(nets), flush=True)
    places = collections.defaultdict(list)
    pattern = rb'\(INSTANNOTATE\s+\(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+\S+\s+\(DEVINSTREF\s+(IOBD|IOBS)\s+\(SITEREF\s+(\d+)\s+(\d+)\)\)\)'
    for m in re.finditer(pattern, raw):
        ident = name(m[1].decode('ascii')); stop = end(raw, m.start())
        places[ident].append({'site': '_'.join(x.decode('ascii') for x in m.groups()[1:]),
                              'evidence': evidence(raw, m.start(), stop)})
    definitions = {}
    def definition(ct):
        if ct not in definitions:
            matches = list(re.finditer(rb'\(CELL '+re.escape(ct.encode('ascii'))+rb'\s', raw[:top_start]))
            assert len(matches) == 1, ('ambiguous definition', ct)
            start = matches[0].start(); stop = end(raw, start)
            definitions[ct] = {'node': parse(raw[start:stop]), 'evidence': evidence(raw, start, stop)}
        return definitions[ct]
    bypin = collections.defaultdict(list)
    for row in pins: bypin[row[0]].append(row)
    rows = []; errors = []; pad_rows = {}
    for report in io:
        port, direction, loc, bank = report[:4]
        assert direction in {'input', 'output', 'inout'}
        direction = {'input': 'INPUT', 'output': 'OUTPUT', 'inout': 'INOUT'}[direction]
        row = {'port': port, 'loc': loc, 'report_bank': bank, 'report_row': report,
               'was_missing_join01': port in old_missing, 'accepted': False}
        rows.append(row)
        try:
            matches = [p for p in bypin[loc] if len(p)>4 and p[4] == port]
            assert len(matches) == 1, ('exact pinout join count', len(matches))
            pinout = matches[0]; row['pinout_row'] = pinout
            row.update(package_site=pinout[1], pinout_bank=pinout[2], function_name=pinout[3])
            fn = re.search(r'(?:DIFFIO|IO)_([LR]\d+)(?:_|$)', pinout[3])
            row['function_derived_bank'] = 'BANK'+fn[1] if fn else None
            top = top_ports[port]
            assert top['locs'] in ([loc], []), ('TOP PAP_IO_LOC mismatch', top['locs'])
            row['loc_binding_source'] = ('exact TOP PAP_IO_LOC plus report/pinout/PLACE' if top['locs'] else
                                         'TOP loc attribute absent; exact report port+loc/pinout plus actual TOP NET endpoint PLACE')
            assert top['direction'] == direction, ('TOP direction mismatch', top['direction'], direction)
            row['top_port'] = top
            idxs = top_connections[port]
            assert len(idxs) == 1, ('TOP NET count', len(idxs))
            conn = nets[idxs[0]]
            endpoints = [(ins, pn) for ins, pn in conn['endpoints'] if ins]
            assert len(endpoints) == 1, ('pad endpoint count', endpoints)
            ins, pad = endpoints[0]; inst = instances[ins]; d = definition(inst['type'])
            operator = name(child(d['node'], 'OPERAREF')[1])
            pad_contract = {'gopIBUF': 'I', 'gopOBUF': 'O', 'gopIOBUF': 'IO',
                            'gopOBUFDSA': 'O', 'gopOBUFDSB': 'O_B',
                            'gopIOBUFDSA': 'IO', 'gopIOBUFDSB': 'IO_B'}
            assert operator in pad_contract and pad == pad_contract[operator], ('pad contract', operator, pad)
            views = [v for v in children(d['node'], 'VIEW') if name(v[1]) == inst['view']]
            assert len(views) == 1
            dp = [p for p in children(child(views[0], 'INTERFACE'), 'PORT') if name(p[1]) == pad]
            assert len(dp) == 1 and child(dp[0], 'DIRECTION')[1] == direction
            placements = places[ins]
            assert len(placements) == 1, ('primitive PLACE count', len(placements))
            assert placements[0]['site'] == pinout[1], ('PLACE != package site', placements[0]['site'])
            row.update(net=conn['net'], net_endpoints=conn['endpoints'],
                       connect_evidence=evidence(raw, *conn['connect_range']),
                       net_evidence=evidence(raw, *conn['net_range']),
                       primitive={'instance': ins, 'type': inst['type'], 'operator': operator,
                                  'pad_pin': pad, 'pad_direction': direction,
                                  'instance_evidence': evidence(raw, *inst['range']),
                                  'definition_ref': inst['type']},
                       actual_PLACE=placements[0])
            row['accepted'] = True; pad_rows[port] = row
        except (AssertionError, KeyError, IndexError) as exc:
            row['error'] = str(exc); errors.append({'port': port, 'error': str(exc)})
    pairs = []
    for positive, negative, bit in [('mem_ck', 'mem_ck_n', None),
                                    ('mem_dqs[0]', 'mem_dqs_n[0]', 0),
                                    ('mem_dqs[1]', 'mem_dqs_n[1]', 1)]:
        pair = {'positive_port': positive, 'negative_port': negative, 'array_bit': bit, 'accepted': False}
        pairs.append(pair)
        try:
            a, b = pad_rows[positive], pad_rows[negative]
            ai, bi = a['primitive']['instance'], b['primitive']['instance']
            ops = (a['primitive']['operator'], b['primitive']['operator'])
            assert ops in [('gopOBUFDSA', 'gopOBUFDSB'), ('gopIOBUFDSA', 'gopIOBUFDSB')]
            assert a['actual_PLACE']['site'].startswith('IOBD_') and b['actual_PLACE']['site'].startswith('IOBS_')
            links = [('DIFFO_OUT', 'DIFFO_IN')] if ops[0] == 'gopOBUFDSA' else [('DIFFI_IN', 'DIFFI_OUT')]
            pair['links'] = []
            for ap, bp in links:
                an, bn = pin_connections[(ai, ap)], pin_connections[(bi, bp)]
                assert len(an) == len(bn) == 1 and an == bn, ('differential link mismatch', ap, bp)
                n = nets[an[0]]
                pair['links'].append({'a_pin': ai+'/'+ap, 'b_pin': bi+'/'+bp,
                                      'net': n['net'], 'endpoints': n['endpoints'],
                                      'connect_evidence': evidence(raw, *n['connect_range'])})
            if ops[0] == 'gopIOBUFDSA':
                # Routed DDR DQS uses a cascade comparator, not DIFFO_OUT/IN.
                def driven_net(ins, pin):
                    idxs = pin_connections[(ins, pin)]
                    assert len(idxs) == 1, ('unique drive net', ins, pin, idxs)
                    n = nets[idxs[0]]
                    others = [(i, p) for i, p in n['endpoints'] if (i, p) != (ins, pin)]
                    assert len(others) == 1, ('unique drive source', others)
                    return n, others[0]
                an, (iol, iol_pin) = driven_net(ai, 'I')
                bn, (cmp, cmp_pin) = driven_net(bi, 'I')
                assert iol_pin == 'DO_P' and cmp_pin == 'O'
                assert name(child(definition(instances[iol]['type'])['node'], 'OPERAREF')[1]) == 'gopIOL'
                assert name(child(definition(instances[cmp]['type'])['node'], 'OPERAREF')[1]) == 'gopIOLOTCMP'
                cn, cascade_source = driven_net(cmp, 'IN')
                tn, ts_source = driven_net(cmp, 'TS')
                assert cascade_source == (iol, 'DO_CAS_OUT') and ts_source == (iol, 'TO_CAS_OUT')
                pair['routed_output_contract'] = {'positive_driver': iol+'/DO_P',
                    'negative_cascade_driver': iol+'/DO_CAS_OUT', 'cascade_comparator': cmp,
                    'cascade_tristate_driver': iol+'/TO_CAS_OUT',
                    'no_direct_DIFFO_link': not pin_connections[(ai, 'DIFFO_OUT')] and not pin_connections[(bi, 'DIFFO_IN')],
                    'actual_nets': [{'net': n['net'], 'endpoints': n['endpoints'],
                                     'connect_evidence': evidence(raw, *n['connect_range'])} for n in [an, bn, cn, tn]],
                    'source_instances': [{'instance': ident, 'type': instances[ident]['type'],
                                          'instance_evidence': evidence(raw, *instances[ident]['range']),
                                          'definition_ref': instances[ident]['type']} for ident in [iol, cmp]]}
            pair.update(positive_instance=ai, negative_instance=bi,
                        positive_pad=a['primitive']['pad_pin'], negative_pad=b['primitive']['pad_pin'],
                        positive_site=a['actual_PLACE']['site'], negative_site=b['actual_PLACE']['site'],
                        bit_contract='exact INDEXED TOP port bit and CONNECT endpoint; separate A/B pad and PLACE; no name-substring or site-only matching',
                        accepted=True)
            a['differential_pair_ref'] = positive; b['differential_pair_ref'] = positive
        except (AssertionError, KeyError) as exc:
            pair['error'] = str(exc)
            for port in [positive, negative]:
                if port in pad_rows: pad_rows[port]['accepted'] = False
                errors.append({'port': port, 'error': 'differential contract: '+str(exc)})
    after = {str(p): sha(p) for p in dict.fromkeys(paths)}
    assert before == after, 'inputs changed during read-only audit'
    accepted = [r for r in rows if r['accepted']]
    conflicts = [r['port'] for r in rows if r.get('function_derived_bank') and
                 r['function_derived_bank'] != r['report_bank']]
    result = {'status': 'PHYSICAL_CONNECTION_ONLY_NOT_INTERNAL_BANK_ACCEPTANCE',
              'inputs': before, 'inputs_unchanged_after_audit': True,
              'prior_graph_binding_audit': bindings,
              'new_graph_binding': {'fulltop_input': str(TARGET), 'fulltop_sha256': sha_bytes(raw),
                                    'top_cell': 'v7_sdt_top', 'top_view': 'v7_sdt_top',
                                    'flattened_hierarchical_INSTREF': True,
                                    'alias_source': 'actual NET/CONNECT/PORTREF in this same fulltop',
                                    'top_cell_byte_range': [top_start, top_end],
                                    'top_interface_evidence': evidence(raw, interface_start, interface_end),
                                    'parser_helpers_sha256': sha(PARSER), 'audit_script_sha256': sha(H/'probe.py')},
              'rows': rows, 'primitive_definitions': definitions, 'differential_pairs': pairs,
              'port_count': len(io), 'accepted_connection_count': len(accepted),
              'join01_missing_count': len(old_missing),
              'newly_resolved_join01_missing_count': sum(r['was_missing_join01'] for r in accepted),
              'errors': errors, 'unresolved_ports': [r['port'] for r in rows if not r['accepted']],
              'physical_join_complete': len(accepted) == 112 and not errors,
              'function_derived_counts': dict(collections.Counter(r.get('function_derived_bank') for r in rows)),
              'report_bank_counts': dict(collections.Counter(r['report_bank'] for r in rows)),
              'pinout_bank_counts': dict(collections.Counter(r.get('pinout_bank') for r in rows)),
              'function_vs_report_conflict_ports': conflicts,
              'internal_bank_metadata_verified': False, 'usedIO_internal_bank_objects_verified': False,
              'IO_gate_passed': False, 'IOgate': False,
              'false_acceptance_policy': 'every accepted row requires exact report port/loc and pinout, exact TOP port/bit (PAP_IO_LOC must agree if present), unique actual CONNECT pad endpoint, primitive pad contract, unique PLACE equal to exact pinout site; errors remain unresolved; FuncName never certifies internal BANK'}
    (H/'join_result.json').write_text(json.dumps(result, indent=2), encoding='ascii')
    sparse = {'fulltop_sha256': sha_bytes(raw), 'script_sha256': sha(H/'probe.py'),
              'top_cell': 'v7_sdt_top',
              'net_aliases': {r['port']: {'net': r.get('net'), 'actual_endpoints': r.get('net_endpoints'),
                                         'byte_range': [r['connect_evidence']['byte_start'], r['connect_evidence']['byte_end_exclusive']]}
                              for r in rows if 'connect_evidence' in r},
              'differential_pairs': pairs, 'IO_gate_passed': False}
    (H/'connection_graph.json').write_text(json.dumps(sparse, indent=2), encoding='ascii')
    report = ['# Actual IO connection evidence (read-only)', '',
              f"Exact physical connections: {len(accepted)}/112; previous missing rows resolved: {result['newly_resolved_join01_missing_count']}/49.",
              f"Unresolved ports: {result['unresolved_ports']}. Differential pair contracts: {sum(p['accepted'] for p in pairs)}/3.",
              '', 'Only this new diagnostic directory was written. No PDS, board operations, build04 changes, installation binary scans, or controllerguard operations were performed.',
              '', 'The existing routed and actual_final_pnr graphs bind to different synthesis exports. Their objects/input hashes were verified and recorded, but neither graph was reused for acceptance. A fresh sparse graph is derived from the requested routed_dump.txt; hierarchical instance paths are exact flattened TOP INSTREF values. The original parser helpers decode ADIF identifiers/INDEXED bits; no substring target-name matching occurs.',
              '', 'Each accepted row joins IO-report port/loc to exactly one pinout row, checks the actual TOP PAP_IO_LOC for the exact scalar/array bit when present, then follows the actual NET/CONNECT/PORTREF to exactly one primitive external pad pin. sfp_tx_disable has no TOP PAP_IO_LOC: its loc is established by exact report/pinout port+loc and the connected primitive PLACE, and the absent attribute is explicitly recorded. Its operator definition establishes the I/O/IO/O_B/IO_B pad contract. The exact INSTREF has one IOBD/IOBS PLACE matching the pinout package site. Raw ADIF, byte ranges (zero-based, end exclusive), snippet hashes, complete input hashes and script hashes are in join_result.json. Rows include full array NET blocks as well as the exact bit CONNECT. connection_graph.json is a sparse graph bound to the same target hash.',
              '', 'mem_ck and mem_ck_n resolve separately to O and O_B, with a verified DIFFO_OUT->DIFFO_IN net. Each mem_dqs[k]/mem_dqs_n[k] resolves separately to IO and IO_B for the same exact TOP bit k, with DIFFI_OUT->DIFFI_IN verified. The final routed DQS output has no direct DIFFO link: the positive I pin is driven by IOL.DO_P; the negative I pin is driven by IOLOTCMP.O, whose IN and TS connect to the same IOL.DO_CAS_OUT and IOL.TO_CAS_OUT. These four actual nets and both source instances/definitions are recorded. Positive and negative pads have their own actual IOBD/IOBS sites. Bit/polarity is not inferred from adjacent sites or an opit substring.',
              '', f"Function-derived counts: {result['function_derived_counts']}. Native IO-report bank counts: {result['report_bank_counts']}. Pinout bank counts: {result['pinout_bank_counts']}.",
              f"FuncName versus native IO-report conflicts: {len(conflicts)}/112; exact ports are listed in JSON.",
              '', 'Physical connection and bank-like function naming remain separate claims. FuncName-derived BANK labels are descriptive package-function inference only. They do not prove native usedIO internal BANK objects, internal bank metadata completeness, or explain away native bank contradictions. internal_bank_metadata_verified=false, usedIO_internal_bank_objects_verified=false, IO_gate_passed=false and IOgate=false are retained.',
              '', '| Port | Loc | Actual net | Primitive pad | PLACE | Accepted |',
              '|---|---|---|---|---|---|']
    for r in rows:
        primitive = r.get('primitive', {})
        report.append(f"| {r['port']} | {r['loc']} | {r.get('net','')} | {primitive.get('instance','')}/{primitive.get('pad_pin','')} | {r.get('actual_PLACE',{}).get('site','')} | {r['accepted']} |")
    (H/'REPORT.md').write_text('\n'.join(report)+'\n', encoding='ascii')
    print(json.dumps({k: result[k] for k in ['accepted_connection_count', 'newly_resolved_join01_missing_count', 'unresolved_ports', 'physical_join_complete', 'function_derived_counts', 'report_bank_counts', 'pinout_bank_counts', 'IO_gate_passed']}, indent=2))

if __name__ == '__main__': main()
