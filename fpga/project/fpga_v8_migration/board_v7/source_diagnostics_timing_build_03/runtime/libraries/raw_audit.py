"""Final routed evidence audit. Only new route-directory outputs are written."""
from pathlib import Path
import collections
import json
import re
import xml.etree.ElementTree as ET
from summarize_route import HERE, EVIDENCE, sha, extract, write
from run_route import guards, inputs

def text(b):
    return b.decode('ascii', 'backslashreplace')

def main():
    result = json.loads((HERE / 'final_export_result.json').read_bytes())
    assert result['exit_code'] == 0 and result['route_db_unchanged'] and result['protected_unchanged']
    db = HERE / 'final_export/report_timing/rtr.db'
    tables = extract(db, 'final_sta')
    write('final_sta_tables.json', tables)
    report_path = HERE / 'final_export/report_timing/v7_sdt_top.rtr'
    report = report_path.read_bytes().decode('ascii', 'backslashreplace')
    summaries = []
    for m in re.finditer(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):(.*?)(?=^=+)', report, re.M | re.S):
        section, corner, block = m.groups()
        entries = []
        for line in block.splitlines():
            cols = line.split()
            if section == 'Minimum Pulse Width' and len(cols) == 5 and re.fullmatch(r'-?\d+\.\d+', cols[1]):
                entries.append({'clock': cols[0], 'worst_slack_ns': float(cols[1]), 'total_negative_slack_ns': float(cols[2]),
                                'failing_endpoints': int(cols[3]), 'total_endpoints': int(cols[4])})
            elif len(cols) == 6 and re.fullmatch(r'-?\d+\.\d+', cols[2]):
                entries.append({'launch': cols[0], 'capture': cols[1], 'worst_slack_ns': float(cols[2]),
                                'total_negative_slack_ns': float(cols[3]), 'failing_endpoints': int(cols[4]), 'total_endpoints': int(cols[5])})
        summaries.append({'section': section, 'corner': corner, 'rows': entries,
                          'sum_failing_endpoints': sum(r['failing_endpoints'] for r in entries)})
    assert len(summaries) == 10
    # Preserve every returned failing path with endpoint/startpoint and full original detail.
    paths = []
    for m in re.finditer(r'(?m)^Startpoint\s*:.*?(?=^Startpoint\s*:|\Z)', report, re.S):
        block = m[0]
        fields = {}
        for name in ['Path Type', 'Startpoint', 'Endpoint', 'Path Group', 'Slack']:
            found = re.search(r'^\s*' + re.escape(name) + r'\s*:\s*(.*)$', block, re.M)
            fields[name] = found[1].strip() if found else None
        slack = re.search(r'Slack \(VIOLATED\)\s+(-?[0-9.]+)', block)
        fields['Slack'] = float(slack[1]) if slack else None
        paths.append({'number': len(paths) + 1, **fields, 'full_detail': block})
    failing = [p for p in paths if p['Slack'] is not None and p['Slack'] < 0]
    unscored = [p for p in paths if p['Slack'] is None]
    write('all_reported_paths.json', paths)
    write('all_reported_failing_paths.json', failing)
    write('unconstrained_io_paths.json', unscored)
    write('final_sta_summary.json', {'report': str(report_path), 'report_sha256': sha(report_path),
                                    'routed_db_sha256': result['route_sha256_after'],
                                    'design_summary': re.findall(r'^Design Summary.*', report, re.M),
                                    'all_corner_summaries': summaries, 'reported_path_count': len(paths),
                                    'negative_slack_paths': len(failing), 'unscored_io_paths': len(unscored),
                                    'negative_paths_match_summary_endpoint_total': len(failing) == sum(s['sum_failing_endpoints'] for s in summaries),
                                    'export_filter': 'slack < 0; nworst 1; max_path 200000',
                                    'tables': list(tables), 'timing_closed': False})
    dump_path = HERE / 'final_export/routed_dump.txt'
    dump = dump_path.read_bytes()
    verilog_path = HERE / 'final_export/routed_dump.v'
    verilog = verilog_path.read_bytes()
    ram = []
    for camera in ['ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top']:
        prefix = camera + '/u_motion_tap/u_detector'
        cells = []
        for bit in range(8):
            name = prefix + '/history_' + str(bit) + '/gopdrm_36k'
            instance = re.search(rb'\(INSTANCE \\' + re.escape(name.encode()) + rb'\s+.*?\n          \)', dump, re.S)
            placement = re.search(rb'\(INSTANNOTATE \(INSTREF \\' + re.escape(name.encode()) + rb'\s+\).*?\n        \)', dump, re.S)
            declaration = re.search(rb'\\' + re.escape(name.encode()) + rb'\s+\(', verilog)
            assert instance and placement and declaration, name
            parameter_start = verilog.rfind(b'gopDRM ', 0, declaration.start())
            assert parameter_start >= 0
            port_end = verilog.index(b');', declaration.start()) + 2
            full_cell = verilog[parameter_start:port_end]
            parameters = dict((text(k), text(v).strip()) for k, v in re.findall(rb'\.(CP_\w+)\(([^)]*)\)', full_cell))
            assert parameters['CP_DRM_36K'] == '"TRUE"'
            assert parameters['CP_WRITE_MODE_A_0'] == '"READ_BEFORE_WRITE"'
            assert parameters['CP_DATA_WIDTH_A_0'] == '1'
            assert (prefix + '/history_q').encode() in full_cell
            assert (prefix + '/sample_address').encode() in full_cell
            assert (prefix + '/current_q').encode() in full_cell or (prefix + '/luma_sum').encode() in full_cell
            file = 'ram_' + camera + '_' + str(bit) + '.v.txt'
            (EVIDENCE / file).write_bytes(full_cell)
            cells.append({'instance': name, 'parameters': parameters, 'definition': text(instance[0]),
                          'physical_placement': text(placement[0]), 'full_verilog_evidence': file})
        ram.append({'instance': prefix, 'logical_depth': 19200, 'logical_width': 8, 'logical_bits': 153600,
                    'geometry_basis': 'byte-identical frozen motion RTL and instantiated baseline geometry; 8 routed 1-bit DRM36K slices with 15-bit address',
                    'mode': 'read_first', 'routed_DRM36K_instances': len(cells), 'cells': cells})
    connections = []
    # Logical CONNECT blocks are bounded at their original indentation.
    all_connections = list(re.finditer(rb'(?m)^            \(CONNECT\b.*?^            \)', dump, re.S))
    for m in all_connections:
        b = m[0]
        if any(k in b for k in [b'/u_motion_tap/u_detector/history_q', b'/u_motion_tap/u_detector/sample_address',
                               b'/u_motion_tap/u_detector/current_q', b'/u_motion_tap/u_detector/history_', b'motion_register_bank', b'u_motion_regs']):
            connections.append(text(b))
    write('motion_ram_connections.json', connections)
    write('motion_routed_resource_proof.json', {'dump_sha256': sha(dump_path), 'verilog_sha256': sha(verilog_path),
                                              'logical_total_bits': 614400, 'routed_history_DRM36K_total': 32,
                                              'histories': ram, 'connect_evidence_blocks': len(connections),
                                              'functional_whole_equivalence_claimed': False})
    base = json.loads((Path(__file__).resolve().parent.parent/'baseline_data/hsst_phy.json').read_bytes())['actual']
    actual_sites = {}
    for name in base['hsst_sites']:
        m = re.search(rb'\(INSTANNOTATE \(INSTREF ' + re.escape(name.encode()) + rb'\s+\).*?\n        \)', dump, re.S)
        assert m, name
        site = re.search(rb'\(PLACE (\S+) \(DEVINSTREF (\S+) \(SITEREF (\d+) (\d+)\)\)\)', m[0])
        assert site, name
        actual_sites[name] = [text(k) for k in site.groups()]
    dedicated = {}
    for port in base['dedicated_connections']:
        # Exact scalar/indexed top NETREF, with connections in the logical model.
        if '[' in port:
            name, index = port.rstrip(']').split('[')
            token = rb'\(PORTREF \(INDEXED ' + re.escape(name.encode()) + rb'\s+' + index.encode() + rb'\)\)'
        else:
            token = rb'\(PORTREF ' + re.escape(port.encode()) + rb'\s*\)'
        matches = [m for m in all_connections if re.search(token, m[0])]
        assert len(matches) == 1, (port, len(matches))
        refs = re.findall(rb'\(PORTREF (\S+) \(INSTREF ([^\s)]+)\s*\)\)', matches[0][0])
        dedicated[port] = [[text(pin), text(inst)] for pin, inst in refs]
    write('hsst_actual_phy_audit.json', {'hsst_sites': actual_sites, 'dedicated_connections': dedicated,
                                       'sites_identical_to_baseline': actual_sites == base['hsst_sites'],
                                       'dedicated_connections_identical_to_baseline': dedicated == base['dedicated_connections'],
                                       'dedicated_top_port_count': len(dedicated), 'dump_sha256': sha(dump_path)})
    protected = json.loads((HERE / 'protected_before.json').read_bytes())
    current = guards()
    assert protected == current, 'Protected tree changed'
    assert inputs() == json.loads((HERE / 'inputs_before.json').read_bytes()), 'Local source changed'
    write('protected_final.json', current)
    print('Final all-corner summary:', [(s['section'],s['corner'],s['sum_failing_endpoints']) for s in summaries])
    print('Detailed negative-slack paths:', len(failing), 'unscored IO paths:', len(unscored), 'motion RAM routed cells: 32; connection blocks:', len(connections))
    print('HSST exact comparison:', actual_sites == base['hsst_sites'], dedicated == base['dedicated_connections'])
    print('Final protected files unchanged:', len(current))

if __name__ == '__main__':
    main()
