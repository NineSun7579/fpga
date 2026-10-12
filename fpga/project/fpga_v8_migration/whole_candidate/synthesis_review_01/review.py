"""Read existing bytes; write this review directory only. No tool execution."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
WHOLE = HERE.parent
ROOT = WHOLE.parents[2]
RUN = WHOLE / 'compile_01/attempt_02'
BASE = ROOT / 'project/motion_100h/run_20261003_212303'
BASE_SYN = ROOT / 'project/motion_100h/work/synthesize'
MIGRATION = WHOLE.parent
READS = {}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def label(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    READS[label(path)] = {'sha256': digest(data), 'bytes': len(data)}
    return data


def load(path):
    return json.loads(read(path))


def save(name, value):
    path = (HERE / name).resolve()
    assert path.parent == HERE, 'Writes must remain directly inside this review'
    if isinstance(value, str):
        data = value.encode('utf-8')
    else:
        data = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    path.write_bytes(data)


def text(data):
    return data.decode('ascii', 'backslashreplace')


def excerpt(path, first, last):
    lines = read(path).splitlines()
    return {'file': label(path), 'first_line': first,
            'lines': [f'{i + 1}: {text(lines[i])}'
                      for i in range(first - 1, min(last, len(lines)))]}


def table(root, tid):
    result = root.find(f"table[@id='{tid}']")
    assert result is not None, tid
    return result


def values(row):
    return [n.text or '' for n in row.findall('data')]


def rows(root, tid, nested=False):
    t = table(root, tid)
    headers = [n.text or '' for n in t.find('column_headers')]
    rr = t.iter('row') if nested else t.findall('row')
    return [dict(zip(headers, values(row))) for row in rr if len(values(row)) == len(headers)]


def verify_manifest(manifest, parent):
    failures = {}
    for rel, expected in manifest.items():
        path = Path(rel)
        if not path.is_absolute():
            path = parent / path
        actual = digest(path.read_bytes()) if path.is_file() else None
        if actual != expected:
            failures[rel] = {'expected': expected, 'actual': actual}
    return {'files': len(manifest), 'differences': failures}


def outside_review_snapshot():
    return {p.relative_to(WHOLE).as_posix(): digest(p.read_bytes())
            for p in WHOLE.rglob('*') if p.is_file() and HERE not in p.parents}


def modules(data):
    normalized = data.replace(b'\r', b'')
    return {text(m[1]): {'data': m[0],
                        'line': normalized[:m.start()].count(b'\n') + 1}
            for m in re.finditer(rb'(?m)^module\s+(\S+).*?^endmodule', normalized, re.S)}


def warn_code(line):
    match = re.match(rb'W:\s*([\w-]+):', line)
    return text(match[1]) if match else 'uncoded_constant_removal'


def grouping(message):
    match = re.search(r"(?:Instance|inst) '?((?:u_v8_|cam5_ov5640_ddr)[^'\s]*)", message)
    if not match:
        return 'other'
    return re.sub(r'\[[^\]]*\]', '[]', match[1])


def main():
    initial = outside_review_snapshot()
    existing = load(WHOLE / 'artifacts/all_candidate_final_sha256.json')
    protected = load(WHOLE / 'artifacts/protected_hashes_final.json')
    source_guard = load(RUN / 'inputs_before.json')
    guard_before = {
        'original_candidate': verify_manifest(existing, WHOLE),
        'external_protected': verify_manifest(protected, ROOT / 'project'),
        'original_source_guard': verify_manifest(source_guard, ROOT),
        'existing_whole_files': len(initial),
    }
    save('guard_before.json', guard_before)
    assert all(not v['differences'] for v in guard_before.values() if isinstance(v, dict)), guard_before

    evidence = load(WHOLE / 'artifacts/pds_evidence.json')
    root = ET.fromstring(read(RUN / 'synthesize/snr.db'))
    base_root = ET.fromstring(read(BASE_SYN / 'snr.db'))
    snr = read(RUN / 'synthesize/fpga_v8_cooperative_top.snr')
    base_snr = read(BASE_SYN / 'top.snr')
    synth_net = read(RUN / 'synthesize/fpga_v8_cooperative_top_syn.vm')
    mm = modules(synth_net)
    checks = {r['Check']: int(r['Number of Issues'])
              for r in rows(root, 'synthesize_check_timing_summary')}
    base_checks = {r['Check']: int(r['Number of Issues'])
                   for r in rows(base_root, 'synthesize_check_timing_summary')}
    hold_rows = rows(root, 'synthesize_report_timing_hold')
    core_hold = next(r for r in hold_rows
                     if r['Launch Clock'] == r['Capture Clock'] == 'ddrphy_sysclk')
    baseline_hold = next(r for r in rows(base_root, 'synthesize_report_timing_hold')
                         if r['Launch Clock'] == r['Capture Clock'] == 'ddrphy_sysclk')
    base_path_rows = rows(base_root, 'synthesize_report_timing_path_hold')
    base_by_pair = {(r['Start Point'], r['End Point']): r for r in base_path_rows}
    hold_table = table(root, 'synthesize_report_timing_path_hold')
    path_headers = [n.text for n in hold_table.find('column_headers')]
    detailed = []
    for row in hold_table.findall('row'):
        record = dict(zip(path_headers, values(row)))
        if float(record['Slack']) >= 0:
            continue
        record['source_attributes'] = {n.text: n.attrib for n in row.findall('data') if n.attrib}
        record['expanded_timing_tables'] = [
            {'id': t.get('id'), 'title': t.get('title'),
             'rows': [[{'text': n.text or '', **n.attrib} for n in rr.findall('data')]
                      for rr in t.findall('row')]}
            for t in row.iter('table')]
        record['classification'] = 'inherited_vendor_DDR'
        record['baseline_correspondence'] = base_by_pair.get((record['Start Point'], record['End Point']))
        detailed.append(record)
    assert len(detailed) == 3 and core_hold['Failing Endpoints'] == '10'
    assert all(r['baseline_correspondence'] for r in detailed)

    log_search = []
    for p in sorted(RUN.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in ('.log', '.snr', '.txt'):
            continue
        data = read(p)
        log_search.append({'file': label(p),
                           'detailed_violated_slacks': data.count(b'Slack (VIOLATED)'),
                           'minus_0_004_occurrences': data.count(b'-0.004')})
    clock_cells = [n.text or '' for n in table(root, 'synthesize_report_clock_network').iter('data')]
    prefetch = ('ddr3/u_ips_ddrc_top/mcdq_rdatapath/mcdq_prefetch_fifo/'
                'ips2l_distributed_fifo/u_ips2l_distributed_fifo_distributed_fifo_v1_0/'
                'ips2l_distributed_sdpram_distributed_fifo_v1_0/')
    start = 'ddr3/u_ips_ddrc_top/mcdq_dcp_top/mcdq_dcp_out/'
    structural_prefetch = []
    for signal, sink in [('o_rid[0]', 'mem_0/DI[0]'), ('o_rid[1]', 'mem_0/DI[1]'),
                         ('o_rid[2]', 'mem_1_0/DI[0]'), ('o_rid[3]', 'mem_1_0/DI[1]'),
                         ('o_rlast', 'mem_1_1/DI')]:
        structural_prefetch.append({
            'start_clock_pin': start + signal + '/CLK',
            'start_data_pin': start + signal + '/Q', 'end_data_pin': prefetch + sink,
            'end_clock_pin': prefetch + sink.rsplit('/', 1)[0] + '/WCLK',
            'launch_clock': 'ddrphy_sysclk', 'capture_clock': 'ddrphy_sysclk',
            'classification': 'inherited_vendor_DDR',
            'timed_violation_reported': any(r['End Point'] == prefetch + sink for r in detailed),
            'slack_ns': -0.004 if any(r['End Point'] == prefetch + sink for r in detailed) else None,
            'clock_network_rows': [s for s in clock_cells
                                   if s.startswith(start + signal + '/CLK ') or
                                   s.startswith(prefetch + sink.rsplit('/', 1)[0] + '/WCLK ')],
        })
    base_proof = load(BASE / 'mapped_provenance.json')
    baseline_adf_hash = digest(read(BASE_SYN / 'top_syn.adf'))
    assert baseline_adf_hash == base_proof['synthesized_sha256']
    routed_proof = load(BASE / 'final_sta_proof.json')
    routed_ddr = [r for r in routed_proof['rows']
                  if r.get('launch') == r.get('capture') == 'ddrphy_sysclk']
    save('hold_paths.json', {
        'status': 'EXISTING_REPORT_HAS_ONLY_THREE_OF_TEN_DETAILED_FAILURES',
        'candidate_core_hold': core_hold, 'baseline_core_hold': baseline_hold,
        'timed_failures': detailed,
        'unlisted_failure_records': 7,
        'classification_limit': 'Three detailed paths are vendor DDR; the other seven cannot be classified as timed failures from this report.',
        'structural_prefetch_metadata_connections': structural_prefetch,
        'structural_evidence_excerpts': [
            {'module': name, 'netlist_line': mm[name]['line'], 'cells': text(mm[name]['data'])}
            for name in ['ips2l_distributed_sdpram_v1_0_distributed_fifo_v1_0_1']],
        'report_inventory': log_search,
        'baseline_provenance': {'synthesized_adf_sha256': baseline_adf_hash,
                                'matches_frozen_mapped_provenance': True,
                                'snr_sha256': digest(base_snr), 'snr_header': text(base_snr.splitlines()[0]),
                                'snr_location': label(BASE_SYN / 'top.snr'),
                                'note': 'SNR is in historical work; the corresponding synthesis ADF matches the frozen run receipt. The frozen run does not contain a separately pinned SNR copy.'},
        'frozen_routed_ddr_rows': routed_ddr,
        'routed_proof_reference': label(BASE / 'final_sta_proof.json'),
        'candidate_post_route_results': None,
        'missing_detail_action': 'A separately authorized read-only timing export from the existing synthesis database would need at least 10 failing checks, full start/end pins and transition labels; no PDS process is launched here.',
        'timing_action': 'Keep RTL/delay/constraints unchanged for these hold estimates; evaluate actual candidate routed hold at slow and fast corners before choosing a fix.',
    })
    # Preserve the three exact text-report path blocks as small diagnostic excerpts.
    lines = snr.splitlines()
    hits = [i for i, line in enumerate(lines) if b'Slack (VIOLATED)' in line]
    ranges = []
    for hit in hits:
        first = next((i for i in range(hit, max(-1, hit - 120), -1)
                      if b'Startpoint:' in lines[i] or b'Start Point:' in lines[i]), max(0, hit - 86))
        ranges.extend(f'{i + 1}: {text(lines[i])}' for i in range(first, min(hit + 3, len(lines))))
        ranges.append('')
    save('reported_hold_paths.txt', '\n'.join(ranges) + '\n')

    new_warning_rows = []
    warning_stage_counts = {}
    for stage, p in [('compile', RUN / 'compile/run.log'), ('synthesis_only', RUN / 'synthesize/run.log')]:
        data = read(p)
        local = []
        for number, line in enumerate(data.splitlines(), 1):
            if not line.startswith(b'W:'):
                continue
            component_source = re.search(rb'/rtl/fpga_v8_(?!cooperative_top\.v)', line)
            component_hierarchy = re.search(rb'u_v8_|cam5_ov5640_ddr', line)
            if component_source or component_hierarchy:
                local.append({'stage': stage, 'file': label(p), 'line': number,
                              'code': warn_code(line), 'message': text(line),
                              'line_sha256': digest(line), 'group': grouping(text(line))})
        new_warning_rows.extend(local)
        warning_stage_counts[stage] = dict(Counter(r['code'] for r in local))
    grouped = defaultdict(list)
    for row in new_warning_rows:
        grouped[(row['stage'], row['code'], row['group'])].append(row)
    categories = [{'stage': stage, 'code': code, 'hierarchy_group': group,
                   'count': len(rr), 'example': rr[0]}
                  for (stage, code, group), rr in sorted(grouped.items())]
    loop_row = next(row for row in table(root, 'synthesize_check_timing_summary').findall('row')
                    if values(row)[0] == 'loops')
    loop_detail = [n.text for n in loop_row.iter('data') if n.text]
    loop_message = [n.text for n in table(root, 'synthesize_messages').iter('data')
                    if 'STA-3001:' in (n.text or '')]
    loop_cells = []
    for name, cell_name in [('fpga_v8_capture_lease', 'N9_1_6'),
                            ('fpga_v8_capture_control_axil', 'N59_9')]:
        m = mm[name]
        cell = next(c for c in re.finditer(rb'GTP_LUT\w+[^;]*;', m['data'])
                    if (cell_name + ' (').encode() in c[0])
        loop_cells.append({'module': name, 'module_netlist_line': m['line'], 'cell': text(cell[0])})
    resources = [r for r in rows(root, 'synthesize_resource_utilization', nested=True)
                 if re.search(r'^u_v8_|^cam5_ov5640_ddr', r['Module Inst Name'])]
    assert all(int(r['LUT']) > 0 for r in resources if r['Module Inst Name'].startswith('u_v8_'))
    save('warnings.json', {
        'counts': warning_stage_counts,
        'scope': 'Direct new-component source warnings plus synthesized u_v8_* and cam5_ov5640_ddr hierarchies; excludes inherited top-path messages.',
        'groups': categories,
        'original_evidence_filter_limit': 'The original new_component_warnings is source-path based and contains the endpoint warning. Hierarchy-only optimization messages and the timing loop need this separate review.',
        'original_new_component_warning': evidence['stages']['compile']['new_component_warnings'],
        'actionable_function_warnings': 1,
        'actionable_new_combinational_loops': checks['loops'],
        'latches': checks['latchs'], 'latch_loops': checks['latch_loops'],
        'baseline_check_timing': base_checks, 'candidate_check_timing': checks,
        'loop_exact_pin_chain': loop_detail, 'loop_message': loop_message,
        'loop_cells': loop_cells,
        'loop_source_chain': [excerpt(WHOLE / 'rtl/fpga_v8_capture_control_axil.v', 66, 70),
                              excerpt(WHOLE / 'rtl/fpga_v8_capture_lease.v', 69, 73),
                              excerpt(WHOLE / 'rtl/fpga_v8_capture_ov5640_ddr.v', 47, 54),
                              excerpt(WHOLE / 'rtl/fpga_v8_capture_ov5640_ddr.v', 105, 112),
                              excerpt(WHOLE / 'inputs/source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v', 94, 94)],
        'loop_interpretation': 'config_ready -> config_valid -> lease_block -> admitted m_vsync -> engine_idle -> config_ready. The ARM/SOF arbitration is combinational feedback; STA cuts a loop arc, so positive setup slack does not establish timing for that feedback.',
        'loop_action': 'Capture owner must remove the feedback in a separately reviewed revision while preserving ARM-before-SOF admission and busy-ARM rejection. Do not hide it with another false path. No correction made here.',
        'core_removed': False, 'resource_attribution': resources,
        'optimization_interpretation': 'Constant address/geometry/CAM_ID specialization, redundant generation/sequence tokens, discarded AXI protection bits and unused debug outputs explain large pruning counts. Resources prove retained logic, not whole mapped equivalence.',
        'visibility_action': 'Detailed DDR/arbiter error flags and several bridge/cam5 debug outputs have no host-visible sink in this API; retain that limitation in integration acceptance.',
    })

    clocks = rows(root, 'synthesize_report_timing_clock_summary', nested=True)
    base_clocks = rows(base_root, 'synthesize_report_timing_clock_summary', nested=True)
    constraints = []
    command_pattern = rb'^\s*(?:create_(?:generated_)?clock|set_(?:clock_groups|clock_uncertainty|multicycle_path|false_path|max_delay|min_delay|input_delay|output_delay))\b'
    for p in sorted((WHOLE / 'inputs/source/constraints').glob('*.fdc')):
        data = read(p)
        frozen = BASE / 'inputs/source/constraints' / p.name
        assert data == read(frozen), p.name
        constraints.append({'file': label(p), 'sha256': digest(data), 'frozen_bytes_identical': True,
                            'commands': [{'line': n, 'command': text(line)}
                                         for n, line in enumerate(data.splitlines(), 1)
                                         if re.search(command_pattern, line)]})
    core_clock = next(c for c in clocks if c['Clock Name'] == 'ddrphy_sysclk')
    base_core_clock = next(c for c in base_clocks if c['Clock Name'] == 'ddrphy_sysclk')
    clock_comparison = {k: {'candidate': core_clock[k], 'baseline': base_core_clock[k]}
                        for k in core_clock if k not in ['Clock Load', 'Non-clock Load']}
    assert all(v['candidate'] == v['baseline'] for v in clock_comparison.values())
    interaction = [r for r in rows(root, 'synthesize_report_clock_interaction')
                   if any(v == 'ddrphy_sysclk' for v in r.values())]
    save('clocks_constraints.json', {
        'candidate_clocks': clocks, 'baseline_clocks': base_clocks,
        'core_clock_comparison': clock_comparison,
        'core_frequency_formula': '25 MHz * 84 / 16 = 131.25 MHz; period 7.6190 ns',
        'core_connections': excerpt(WHOLE / 'rtl/fpga_v8_cooperative_top.v', 355, 358),
        'separate_150mhz_clock': 'clk_150m at ov5640_clk/u_gpll/CLKOUT1 is generated at 150 MHz with zero reported clock loads; it is not core_clk/axi_clk.',
        'constraint_files': rows(root, 'synthesize_constraint_files'),
        'constraint_lineage': constraints, 'ddr_clock_interactions': interaction,
        'cdc_lineage': 'clock.fdc separates camera, PCIe, free/rst, SFP and DDR groups asynchronously. cdc.fdc has no active create_clock/set_false_path/set_max_delay command. Historical whole-FIFO false paths are commented out. The orphan continuation text after commented max-delay commands remains inherited; it does not constitute a verified Gray-pointer delay constraint.',
        'ddr_phy_exceptions': 'clock.fdc:34-41 retains DDR-to-PHY setup=2/hold=1 multicycle and 0.4 ns uncertainty; clock.fdc:73-77 also separates PHY/core groups asynchronously. Clock-interaction records, not declarations alone, determine effective cuts.',
        'reset_timing_limit': '62 inputs lack input delay and 71 outputs lack output delay; no_clock=0, virtual_clock=1. Asynchronous grouping/positive recovery/removal estimates do not prove metastability safety, reset synchronization, or coordinated reset recovery.',
    })

    endpoint_path = MIGRATION / 'component_synthesis/endpoint_netlist_sim_01/results.json'
    endpoint = load(endpoint_path)
    bindings = load(WHOLE / 'artifacts/component_binding.json')
    endpoint_inputs = {}
    for filename, expected in endpoint['inputs'].items():
        actual = digest(read(Path(filename)))
        endpoint_inputs[filename] = {'expected': expected, 'actual': actual, 'matches': actual == expected}
    assert all(r['matches'] for r in endpoint_inputs.values())
    assert endpoint['status'] == 'PASS' and endpoint['operations'] == 654 and endpoint['mapped']['events'] == 3913
    for name in ['cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v',
                 'cooperative_control/fpga_v8_coop_control_axil.v']:
        assert digest(read(MIGRATION / name)) == bindings[name]
    correction = MIGRATION / 'pcie_h2f_transport_contract/artifacts'
    correction_results = load(correction / 'results.json')
    correction_manifest = load(correction / 'edit_manifest.json')
    correction_negative = load(correction / 'negative_evidence.json')
    wrapper_files = ['fpga_v8_pcie_fifo_h2f.v', 'fpga_v8_pango_pcie_top_h2f.v',
                     'fpga_v8_pcie_dma_h2f.v', 'fpga_v8_pcie_dma_controller_h2f.v']
    correction_bindings = {}
    correction_chain = []
    for filename in wrapper_files:
        data = read(correction / filename)
        expected = correction_manifest[filename]['sha256']
        assert digest(data) == expected, filename
        correction_bindings[filename] = {'file': label(correction / filename), 'sha256': expected,
                                        'api_identical_receipt': correction_manifest[filename]['api_identical']}
        correction_chain.append({'file': label(correction / filename),
                                 'module_and_candidate_child_lines': [
                                     {'line': n, 'text': text(line)}
                                     for n, line in enumerate(data.splitlines(), 1)
                                     if re.search(rb'\b(?:module\s+fpga_v8_|fpga_v8_(?:pango_pcie_top_h2f|pcie_dma_h2f|pcie_dma_controller_h2f)\s*#)', line)]})
    retirement = load(MIGRATION / 'pcie_retirement_contract/artifacts/results.json')
    read(MIGRATION / 'pcie_retirement_contract/REPORT.md')
    read(MIGRATION / 'pcie_h2f_transport_contract/README.md')
    registered = []
    project = read(WHOLE / 'project.pds')
    for n, line in enumerate(project.splitlines(), 1):
        if re.search(rb'pcie_fifo\.v|pango_pcie_top\.v|ips2l_pcie_dma(?:_controller)?\.v', line):
            registered.append({'line': n, 'text': text(line)})
    old_chain = [
        {'file': 'rtl/fpga_v8_cooperative_top.v', 'type_line': 446, 'instance_line': 449,
         'module': 'pcie_fifo', 'instance': 'pcie_fifo'},
        {'file': 'inputs/source/pcie_dma/pcie_fifo.v', 'type_line': 216, 'instance_line': 220,
         'module': 'pango_pcie_top', 'instance': 'pcie_fifo/pango_pcie_top'},
        {'file': 'inputs/source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v', 'type_line': 349, 'instance_line': 354,
         'module': 'ips2l_pcie_dma', 'instance': 'pcie_fifo/pango_pcie_top/u_ips2l_pcie_dma'},
        {'file': 'inputs/source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma.v', 'type_line': 328, 'instance_line': 332,
         'module': 'ips2l_pcie_dma_controller',
         'instance': 'pcie_fifo/pango_pcie_top/u_ips2l_pcie_dma/u_ips2l_pcie_dma_controller'},
    ]
    for record in old_chain:
        path = WHOLE / record['file']
        record['sha256'] = digest(read(path))
        record['source_excerpt'] = excerpt(path, record['type_line'], record['instance_line'] + 7)
    reset_evidence = [excerpt(WHOLE / 'rtl/fpga_v8_cooperative_top.v', 243, 256),
                      excerpt(WHOLE / 'rtl/fpga_v8_cooperative_top.v', 355, 358),
                      excerpt(WHOLE / 'rtl/fpga_v8_cooperative_top.v', 446, 474),
                      excerpt(WHOLE / 'inputs/source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v', 68, 69),
                      excerpt(WHOLE / 'inputs/source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v', 203, 241),
                      excerpt(WHOLE / 'inputs/source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v', 349, 361),
                      excerpt(WHOLE / 'inputs/source/pcie_dma/pcie_fifo.v', 266, 279)]
    save('integration.json', {
        'whole_revision_created': False, 'existing_pds_registered_chain': old_chain,
        'existing_pds_registration_lines': registered, 'new_candidate_bindings': correction_bindings,
        'new_candidate_chain_receipt': correction_chain,
        'correction_status_at_read': correction_results['status'],
        'correction_cases': correction_results['cases'],
        'correction_fault_cases': correction_results['fault_cases'],
        'correction_event_counts': correction_results['event_counts'],
        'correction_scope': correction_results['scope'],
        'independent_resets_supported': correction_results['independent_resets_supported'],
        'f2h_retirement_validated': correction_results['f2h_retirement_validated'],
        'linux_completion_validated': correction_results['linux_completion_validated'],
        'correction_negative_evidence': correction_negative,
        'old_msi_example': retirement['implementations']['baseline']['control'][0],
        'original_pending_fields_verbatim': evidence['pending'],
        'endpoint_separate_reference': {'file': label(endpoint_path), 'status': endpoint['status'],
                                        'operations': endpoint['operations'], 'events': endpoint['mapped']['events'],
                                        'protocol_errors': endpoint['mapped']['protocol_errors'],
                                        'omitted_internal_reset_kinds': endpoint['omitted_internal_reset_kinds'],
                                        'comparisons': endpoint['comparisons'], 'inputs_verified': endpoint_inputs,
                                        'matches_current_endpoint_and_coop_control_bindings': True,
                                        'whole_mapped_equivalence': False},
        'reset_source_evidence': reset_evidence,
        'reset_domains': {'pcie_clk': 'pclk_div2, 125 MHz', 'pcie_rst': '~core_rst_n',
                         'axi_clk': 'DDR core_clk / ddrphy_sysclk, 131.25 MHz',
                         'axi_rst': '~ddr_init_done',
                         'coordinated_epoch_reset_implemented': False,
                         'availability': 'button_rst_n and perst_n feed PCIe debounce/core reset only; DDR rst_n is 1\'b1. There is no demonstrated common host-triggerable reset that clears PCIe/controller/FIFO and AXI fabric/endpoint together.'},
        'next_revision_scope': 'Four unique candidate modules and one top module-type rebinding, preserving instance names and all hard-IP dependencies. Register exact artifact bytes with explicit timespec, unique top and isolated paths. No protected source/IP edits.',
        'integration_gate': 'Read-only correction receipt exists and hashes match. Parent artifact review, coordinated reset, connected mapped simulation, F2H/Linux completion proof and route remain pending; no next revision is built here.',
    })

    warning_counts = warning_stage_counts['synthesis_only']
    compact_resources = '\n'.join(
        f"| {r['Module Inst Name']} | {r['LUT']} | {r['FF']} | {r['Distributed RAM']} | {r['DRM']} |"
        for r in resources if '/' not in r['Module Inst Name'])
    path_md = '\n'.join(f"| {i} | `{r['Start Point']}` | `{r['End Point']}` | {r['Slack']} |"
                        for i, r in enumerate(detailed, 1))
    report = f"""# Existing synthesis review 01

This review reads existing reports and source bytes and writes only this directory. It launches no PDS process, compile, synthesis, map, route, simulator, SSH, or board operation. The original `artifacts/pds_evidence.json`, its pending fields, completed `compile_01`, frozen baseline, component snapshots and dependencies remain unchanged.

**Hold evidence and its limit.** The candidate slow-corner `ddrphy_sysclk -> ddrphy_sysclk` synthesis summary is WHS **−0.004 ns**, THS **−0.040 ns**, **10 failing endpoints** out of 53,444. The existing `.snr` and XML `snr.db` expose only **three detailed failures** for this clock pair; none of the existing full logs exposes the other seven. Thus the requested ten exact timed endpoint records cannot be recovered under this no-PDS-process scope. `hold_paths.json` keeps this gap explicit; netlist connectivity is not assigned invented slack or treated as proof of the omitted failures.

| Reported path | Exact launch clock pin | Exact destination data pin | Slack (ns) |
| --- | --- | --- | ---: |
{path_md}

All three use rise-rise `ddrphy_sysclk` clocks, launching from GTP_DFF_C and capturing into GTP_RAM32X2DP. Source is `inputs/ipcore/ddr3/rtl/mcdq_ctrl/ips2l_mcdq_dcp_out_v1_2.vp:422`; destination is the vendor distributed FIFO SDPRAM `.vp:180`. Both clock trees originate at `free_clk -> ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/CLKOUT0 -> u_sysclk_bufg/CLKOUT -> axi_clk`. Exact tree rows, source/destination file attributes and requirement/arrival calculations are in `hold_paths.json`; text blocks are in `reported_hold_paths.txt`.

The candidate detailed paths have launch clock delay **8.606 ns**, capture clock delay **8.934 ns**, skew **0.328 ns**, data delay **0.588 ns** (0.203 logic + 0.385 estimated route), arrival **9.194 ns** and required **9.198 ns**. They are wholly inherited vendor DDR paths. The additional o_rid[3] and o_rlast connections to the same metadata prefetch RAM are recorded as structural evidence with null unreported slack. We cannot classify the other seven reported failing checks as inherited or cooperative from the available export.

**Motion correspondence.** The historical motion synthesis has the same WHS/THS/failing count **−0.004/−0.040/10**, out of 46,777 endpoints, and the same three exact start/end pairs and data/skew numbers. Its launch/capture delays are **8.781/9.109 ns**, shifted together by 0.175 ns. The historical work synthesis ADF hash `{baseline_adf_hash}` matches the frozen run's `mapped_provenance.json`; the SNR is located in historical work and does not have a separately pinned copy in the frozen run. This provenance limit is retained.

These are **pre-route synthesis estimates**, including estimated route delay. The frozen motion `final_sta_proof.json` separately reports routed same-clock DDR hold **+0.158 ns slow / +0.118 ns fast**, and setup **+0.030 ns slow**. This is baseline domain-wide routed evidence, not a candidate route or exact-path correspondence certificate. It demonstrates that the inherited estimate can close after routing; it cannot promise candidate closure. Leave hold-path RTL, delay and constraints unchanged until actual candidate route exists.

**Actionable warning findings.** There is **one unique endpoint function warning**, repeated in compile and the combined synthesis log: `Verilog-2021`, `eligible.addr_end_1` has no driver and is tied to zero, source line 81. RTL explicitly assigns its 33-bit addr_end expression, so this is a synthesis interpretation warning requiring behavior evidence, not a source variable left unassigned. The separate endpoint component receipt verifies **654 operations / 3,913 events**, zero protocol errors and identical RTL/mapped event hashes. Endpoint and cooperative-control source hashes match the current whole bindings. Internal reset kinds 2, 3 and 5 were omitted by that mapped suite. This receipt does **not** validate whole mapped behavior, capture control, the lease/wrapper loop, or PCIe retirement. The original pending fields are preserved exactly.

There is also **one new combinational loop**, baseline loops=0, candidate loops=1; **latches=0 and latch loops=0**. Its exact loop is `u_v8_capture_lease/N9_1_6/Z -> u_v8_capture_control/N59_9/I0 -> N59_9/Z -> u_v8_capture_lease/N9_1_6/I5 -> N9_1_6/Z`. The merged LUTs output `config_ready` and `config_valid`. RTL lineage is control config_valid (control:69-70) -> lease_block (lease:72-73) -> wrapper SOF admission (wrapper:107 / w_en:94) -> engine_idle (wrapper:53) -> config_ready (lease:71). `STA-3001` explicitly says loop timing arcs are set to false path. ARM and SOF priority can have ambiguous combinational fixed points; positive setup slack is not closure for this feedback. The capture owner needs a separately reviewed correction that preserves ARM-before-SOF admission and busy-ARM rejection. No RTL correction or new false path is introduced in this review.

The synthesis-only new cooperative/cam5 hierarchies contain **{warning_counts.get('Public-4008', 0)} Public-4008 dangling-instance removal warnings** and **{warning_counts.get('uncoded_constant_removal', 0)} constant-bit removal warning lines**. These are line counts across optimization passes, not that many lost functions. `warnings.json` groups them by hierarchy and keeps examples. The original evidence's source-path-only `new_component_warnings` list does not count these hierarchy-only messages. Geometry/CAM_ID/alignment constants, zero AXI response bits, discarded protection bits, redundant token/sequence/generation state and unused diagnostics explain pruning categories. Several diagnostic outputs really have no host-visible consumer; that API visibility limitation remains open.

| Retained top instance | LUT | FF | Distributed RAM | DRM |
| --- | ---: | ---: | ---: | ---: |
{compact_resources}

The resource tree and synthesized instances retain the endpoint, router, capture control/lease, RAW bridge/preprocessing, cooperative write arbiter and DDR adapter. The cooperative core has **1,674 LUT / 1,416 FF** and was not removed. This is structural/resource evidence; whole mapped equivalence remains unproven.

**Clock and constraints.** The DDR common clock is unchanged: **25 MHz × 84 / 16 = 131.25 MHz**, period **7.6190 ns**, source `ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/CLKOUT0`. `core_clk` is the DDR core output, `axi_clk=core_clk`, `axi_rst=~ddr_init_done`. The separate clk_150m generated clock has zero reported clock loads and is not the cooperative clock. All six registered FDC files are byte-identical to frozen inputs. `clocks_constraints.json` records every active clock/group/exception command, its line and hash, actual clock summaries and DDR clock interactions.

Inherited clock.fdc generates camera SCCB clocks, camera pixel clocks, DDR PHY clocks, PCIe 250/125/100 MHz and SFP 125 MHz. It declares asynchronous domain groups. DDR/PHY multicycle setup=2, hold=1 and 0.4 ns uncertainty declarations coexist with asynchronous group cuts; inspect the extracted effective interactions before relying on those cross-clock paths. cdc.fdc has no active false-path or max-delay command; historical whole-FIFO cuts and Gray-pointer max-delay statements are commented out. This preserves same-clock FIFO timing but does not certify CDC transport or reset release. Check Timing reports 62 inputs without input delay, 71 outputs without output delay, zero no_clock and one virtual_clock. Reset-domain limitations and lack of a coordinated PCIe/AXI epoch reset remain explicit in the integration checklist.

Read `integration_checklist.md` for exact old registrations, correction artifact hashes, replacement chain and reset gates. The correction files were available at review time with `{correction_results['status']}` ({correction_results['cases']} cases, {correction_results['fault_cases']} fault cases); this changes only the separate reference status. No candidate v2 is created, copied, registered or built. F2H retirement, Linux completion, independent reset recovery and whole integration are still unvalidated.
"""
    save('REVIEW.md', report)
    chain_md = '\n'.join(f"| `{r['file']}:{r['type_line']}` | `{r['module']}` | `{r['instance']}` |"
                         for r in old_chain)
    replacements = '\n'.join(f"| `{filename}` | `{record['sha256']}` |"
                             for filename, record in correction_bindings.items())
    save('integration_checklist.md', f"""# Next revision integration checklist (no integration performed)

The existing top still binds the original PCIe FIFO and controller. Concrete old hierarchy and PDS registrations are in `integration.json`.

| Candidate-local source and line | Existing module type | Existing instance hierarchy |
| --- | --- | --- |
{chain_md}

Candidate PDS registrations: `ips2l_pcie_dma.v:590`, `ips2l_pcie_dma_controller.v:594`, `pango_pcie_top.v:666`, `pcie_fifo.v:674` (line numbers refer to project.pds). The baseline top's PCIe instance is retained as `pcie_fifo` at top:449; its type begins at top:446. Frozen and candidate-local wrappers are byte-bound in the source receipts.

**Required binding chain.** A later isolated top must change its module type to `fpga_v8_pcie_fifo_h2f` while retaining instance `pcie_fifo`. That candidate binds `fpga_v8_pango_pcie_top_h2f` at retained instance `pango_pcie_top`; that wrapper binds `fpga_v8_pcie_dma_h2f` at `u_ips2l_pcie_dma`; that wrapper binds `fpga_v8_pcie_dma_controller_h2f` at `u_ips2l_pcie_dma_controller`. Merely registering the new controller leaves the old ips2l_pcie_dma controller binding active. All four unique artifacts are therefore required; no hard-IP RTL, configuration or vendor registration needs changing.

Artifacts read from `../pcie_h2f_transport_contract/artifacts/` relative to whole_candidate's parent:

| Artifact | Verified SHA-256 |
| --- | --- |
{replacements}

At read time their edit-manifest hashes matched and API-identical receipts were true. The correction receipt is `{correction_results['status']}`: **{correction_results['cases']} cases**, **{correction_results['fault_cases']} fault cases**, AW 9,925, W 158,368, B 9,924, MSI 41. Its scope is the actual controller and MRD segmenter plus official FIFO/DRM with a simulated PCIe completion/RAM shell. This is separate source evidence and is not a whole integration acceptance. Original whole PDS pending fields remain untouched.

**Inherited defect.** The original pcie_fifo:189-203 raises fpga_rx_done from RAM count/FIFO empty or intermediate chunk completion without accepted AXI B retirement. The DMA wrapper:338 feeds its inverse to controller i_mrd_rx_busy; controller:719 and 942-953 detect completion, controller:992-1006 issues MSI, and ips2l_pcie_dma:112-127 stretches the pulse to grant. The old measured CLAIM MSI is **1.064 us**, full B **1.735 us**, **671 ns early**. The retirement-only predecessor still drops singleton WVALID under a post-AW W stall and permits a 4KB-crossing host chunk at +4. The current correction artifacts separately address W reservation/backpressure, byte reassembly and controller 4KB chunking; binding the retirement-only FIFO cannot claim these fixes.

- [ ] Parent review must pin the complete correction artifact set, exact edit-manifest, results and source hashes before creating a separately authorized next whole revision. No new whole source is generated in this review.
- [ ] In the later isolated revision, copy only these four approved unique modules into its own RTL tree, bind the chain above, register source timespec fields and select a unique top. Keep the old instance names so PCIe clock/HSST/pin constraint hierarchies continue to resolve. Keep protected pcie_fifo, pango_pcie_top, ips2l_pcie_dma, controller and hard-IP bytes untouched.
- [ ] Verify API/parameter equality, candidate module uniqueness, elaborated controller binding, reachable hierarchy and no accidental simultaneous old/new writer use. Use production artifact names, not the ModelSim compatibility `candidate_fifo.v`/`candidate_controller.v` aliases.
- [ ] Verify the corrected H2F path in the connected whole netlist: WREADY before AW, first and later W stalls, stable WDATA/WSTRB/WLAST under stall, partial final strobes, +4/+8/+12 host offsets, 4KB boundaries, 64-bit host address carry, back-to-back chunks and backpressure across the actual crossbar/M02/control path.
- [ ] Verify final completion follows accepted matching ID-zero B; wrong BID, held final B and intermediate errors must keep completion pending. MSI delivery qualifies only the proved retirement boundary; use ordered register readback to resolve accepted/rejected commands because BRESP is not exposed by this ioctl API.
- [ ] Resolve the capture ARM/SOF combinational loop with the capture owner and rerun connected mapped behavior. The endpoint 654-operation mapped receipt does not include the whole lease/wrapper feedback path.
- [ ] Define and implement a coordinated transaction epoch reset, with synchronized release in both domains, for PCIe/controller/FIFO plus crossbar/endpoint/AXI state. Verify it abandons pending work without credit/MSI, drains or clears both FIFO sides consistently and restarts with a new generation. Independent resets are unsupported by the correction receipt.
- [ ] Keep F2H posted-write/MSI ordering, Linux ioctl completion semantics, hard-IP link/completion recovery and board behavior separately pending. Whole mapped checks, route setup/hold at both corners, and hardware acceptance require their own evidence and authorization.

**Actual clock/reset domains.** pango_pcie_top:68-69 drives `fifo_pcie_clk=pclk_div2` (**125 MHz**) and `fifo_pcie_rst=~core_rst_n`. Its DMA/controller use pclk_div2/core_rst_n at pango_pcie_top:356-359 and DMA:334-335. button_rst_n and perst_n feed ref_clk (**100 MHz**) debounce/synchronizers at pango_pcie_top:203-241 and the hard PCIe wrapper reset inputs at 555-564. The AXI side uses DDR core/axi_clk (**131.25 MHz**) and `axi_rst=~ddr_init_done`, with endpoint/control rst_n `~axi_rst`. RX FIFO write reset is fifo_pcie_rst and read reset is axi_rst (pcie_fifo:266-279); TX reverses domains (pcie_fifo:471-489). The existing DDR instance ties rst_n **1'b1** at top:247. Neither button nor PERST demonstrates a shared reset for these states. A coordinated host-triggerable reset is **not implemented or available as a validated contract** in the existing whole top. CPU restart, MSI clear or only one side's reset is not epoch recovery.
""")
    after = outside_review_snapshot()
    differences = {p: {'before': initial.get(p), 'after': after.get(p)}
                   for p in sorted(set(initial) | set(after)) if initial.get(p) != after.get(p)}
    guard_after = {
        'whole_outside_review_differences': differences,
        'original_candidate': verify_manifest(existing, WHOLE),
        'external_protected': verify_manifest(protected, ROOT / 'project'),
        'original_source_guard': verify_manifest(source_guard, ROOT),
        'all_read_references_unchanged': all(digest(Path(ROOT / p).read_bytes()) == r['sha256']
                                           for p, r in READS.items()),
        'pds_evidence_pending_unchanged': load(WHOLE / 'artifacts/pds_evidence.json')['pending'] == evidence['pending'],
        'no_child_processes_launched': True,
        'no_rtl_project_constraint_edits': True,
    }
    save('guard_after.json', guard_after)
    assert not differences and guard_after['all_read_references_unchanged'], guard_after
    assert all(not v['differences'] for v in guard_after.values() if isinstance(v, dict) and 'differences' in v)
    save('read_manifest.json', READS)
    save('review_receipt.json', {
        'status': 'AUDIT_COMPLETE_WITH_EXPLICIT_EXISTING_REPORT_LIMIT',
        'hold_failures': 10, 'detailed_hold_paths_available': 3,
        'detailed_hold_paths_inherited_vendor_ddr': 3, 'remaining_failures_unenumerated': 7,
        'new_endpoint_function_warnings': 1, 'new_combinational_loops': 1,
        'latches': 0, 'latch_loops': 0,
        'hierarchy_optimization_warning_counts': warning_counts,
        'whole_outside_review_files_verified': len(initial),
        'external_protected_files_verified': len(protected),
        'source_guard_files_verified': len(source_guard),
        'new_revision_built': False, 'candidate_route_available': False,
        'original_evidence_pending_unchanged': True,
    })
    manifest = {p.name: digest(p.read_bytes()) for p in HERE.iterdir()
                if p.is_file() and p.name != 'review_sha256.json'}
    save('review_sha256.json', manifest)
    print(json.dumps(load(HERE / 'review_receipt.json'), indent=2))


if __name__ == '__main__':
    main()
