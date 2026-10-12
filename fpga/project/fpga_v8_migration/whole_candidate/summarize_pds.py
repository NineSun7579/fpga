"""Extract preliminary PDS evidence without launching any implementation process."""
from pathlib import Path
from collections import Counter
import fnmatch
import hashlib
import json
import re
import sys
from build_candidate import HERE, BASE, TOP_NAME, COMPONENTS, save, write_json, protected_hashes, ports
from audit_candidate import pin_header


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ascii_text(b):
    return b.decode('ascii', 'backslashreplace')


def warning_key(line):
    # Match historical warnings after removing only workspace, top rename and line annotation.
    s = ascii_text(line).replace(TOP_NAME, 'top')
    s = re.sub(r'\(line number: \d+\)', '(line number: *)', s)
    s = re.sub(r'\[([^\]]+)/((?:inputs/)?(?:source|ipcore)/[^\]]+)',
               lambda m: '[' + m[2].replace('inputs/', ''), s)
    return re.sub(r'\[[^\]]+/rtl/top.v', '[source/top.v', s)


def main():
    assert len(sys.argv) == 2 and re.fullmatch(r'attempt_[0-9]{2}', sys.argv[1])
    run = HERE / 'compile_01' / sys.argv[1]
    evidence = run / 'evidence'
    before = json.loads((run / 'protected_before.json').read_bytes())
    protected = protected_hashes()
    assert all(protected.get(p) == h for p, h in before.items()), 'Protected file hash changed'
    initial = json.loads((run / 'inputs_before.json').read_bytes())
    assert all(sha(Path(p)) == h for p, h in initial.items()), 'Run source hash changed'
    bindings = json.loads((HERE / 'artifacts/component_binding.json').read_bytes())
    assert all(sha(HERE.parent / rel) == sha(HERE / 'rtl' / Path(rel).name) == bindings[rel]
               for rel in COMPONENTS), 'Final component owner binding changed'
    base_log = BASE / 'compile.log'
    old_warnings = Counter(warning_key(l) for l in base_log.read_bytes().splitlines() if l.startswith(b'W:'))
    frozen_synth_warnings = Counter(warning_key(l) for l in (BASE / 'synthesize.log').read_bytes().splitlines()
                                    if l.startswith(b'W:'))
    stages, receipts, logs = {}, {}, {}
    for action in ['compile', 'synthesize']:
        result_file = run / f'{action}_result.json'
        assert result_file.is_file(), f'Wait for completion notification: {action}'
        result = json.loads(result_file.read_bytes())
        log = run / f'{action}_shell.log'
        assert sha(log) == result['shell_log_sha256']
        receipts[action] = result
        text = log.read_bytes()
        logs[action] = text
        warnings = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.startswith(b'W:'):
                continue
            match = re.match(rb'W:\s+([A-Za-z]+-[0-9]+):', line)
            code = ascii_text(match[1]) if match else 'uncoded'
            component = b'/rtl/fpga_v8_' in line and (b'/rtl/' + TOP_NAME.encode() + b'.v') not in line
            top = (b'/rtl/' + TOP_NAME.encode() + b'.v') in line
            warnings.append({'log_line': number, 'code': code, 'message': ascii_text(line),
                             'line_sha256': hashlib.sha256(line).hexdigest(),
                             'source_class': 'new_component' if component else 'candidate_top' if top else 'inherited_or_tool',
                             'matches_frozen_compile_warning': warning_key(line) in old_warnings,
                             'matches_frozen_synthesis_warning': warning_key(line) in frozen_synth_warnings})
        write_json((evidence / f'{action}_warnings.json').relative_to(HERE).as_posix(), warnings)
        save(evidence / f'{action}_warnings.txt', '\n'.join(w['message'] for w in warnings) + '\n')
        stages[action] = {
            'exit_code': result['exit_code'], 'pass': result['pass'],
            'warning_count': len(warnings), 'warning_codes': dict(Counter(w['code'] for w in warnings)),
            'constant_probe_loop_warning_count': sum('Loop was found during constant probe.' in w['message'] for w in warnings),
            'constraint_editor_warnings': [w for w in warnings if w['code'].startswith('ConstraintEditor-')],
            'new_component_warnings': [w for w in warnings if w['source_class'] == 'new_component'],
            'candidate_top_warnings_not_in_frozen_compile': [w for w in warnings
                if w['source_class'] == 'candidate_top' and not w['matches_frozen_compile_warning']],
            'source_inputs_unchanged': result['source_inputs_unchanged'],
            'shell_log': log.relative_to(HERE).as_posix(), 'shell_log_sha256': sha(log),
            'receipt': result_file.relative_to(HERE).as_posix(), 'receipt_sha256': sha(result_file),
        }
    compile_text = logs['compile']
    selection = b'I: Module "' + TOP_NAME.encode() + b'" is set as top module.'
    assert selection in compile_text, 'Wrong PDS top selected'
    all_elaborated = sorted(set(re.findall(rb'Elaborating module (\w+)', compile_text)))
    required = [TOP_NAME.encode()] + [Path(rel).stem.encode() for rel in COMPONENTS]
    assert all(name in all_elaborated for name in required), 'Missing cooperative elaboration'
    project = run / 'project.pds'
    registrations = []
    for rel in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project.read_bytes()):
        p = (run / ascii_text(rel)).resolve()
        assert p.is_relative_to(HERE) and p.is_file(), rel
        registrations.append({'path': p.relative_to(HERE).as_posix(), 'sha256': sha(p)})
    structural = json.loads((HERE / 'artifacts/structural_audit.json').read_bytes())
    source_ports = ports(pin_header((HERE / f'rtl/{TOP_NAME}.v').read_bytes()),
                         {'MEM_ROW_WIDTH': 15, 'MEM_BANK_WIDTH': 3, 'MEM_COLUMN_WIDTH': 10,
                          'MEM_DQ_WIDTH': 16, 'MEM_DQS_WIDTH': 2})
    port_queries = []
    for p in (HERE / 'inputs/source/constraints').glob('*.fdc'):
        content = re.sub(rb'(?m)#.*$', b'', p.read_bytes())
        for query in re.findall(rb'\[get_ports\s+(\{[^}]*\}|[^]\s]+)', content):
            for token in ascii_text(query).strip('{}').split():
                matches = [name for name in source_ports if fnmatch.fnmatchcase(name, token)]
                port_queries.append({'file': p.relative_to(HERE).as_posix(), 'query': token, 'matches': matches})
    assert all(q['matches'] for q in port_queries), 'Unmatched get_ports constraint'
    snr_paths = list((run / 'synthesize').glob('*.snr'))
    snr_report = None
    if receipts['synthesize']['pass']:
        assert len(snr_paths) == 1, snr_paths
        snr = snr_paths[0]
        lines = snr.read_bytes().splitlines()
        content = '\n'.join(ascii_text(l) for l in lines)
        totals = {}
        for name, used, capacity, percent in re.findall(
                r'^Total ([\w /]+)\s*[:=]\s*([0-9.]+) of ([0-9.]+) \(([0-9.]+)%\)', content, re.M):
            totals[name.strip()] = {'used': float(used), 'capacity': float(capacity), 'percent': float(percent)}
        assert 'LUTs' in totals and 'Registers' in totals and 'DRM' in totals, 'Unrecognized SNR resources'
        cells = {ascii_text(name): int(count) for name, count in re.findall(
            rb'(?m)^\s*(GTP_\w+)\s+(\d+)\s+uses?\s*$', snr.read_bytes())}
        performance = {}
        for name, request, estimate, req_period, est_period, slack in re.findall(
                r'^\s*(\w+)\s+([0-9.]+) MHz\s+([0-9.]+) MHz\s+([0-9.]+)\s+([0-9.]+)\s+(-?[0-9.]+)\s*$', content, re.M):
            performance[name] = {'requested_mhz': float(request), 'estimated_mhz': float(estimate),
                                 'requested_period_ns': float(req_period), 'estimated_period_ns': float(est_period),
                                 'setup_slack_ns': float(slack)}
        assert abs(performance['ddrphy_sysclk']['requested_mhz'] - 131.25) < 0.001
        timing_start = content.index(' Performance Summary:')
        # Summary tables precede the first detailed timing path.
        path_start = re.search(r'^\s*Path(?: Group| #| \d| Type)', content[timing_start:], re.M)
        timing_end = timing_start + path_start.start() if path_start else min(len(content), timing_start + 19000)
        save(evidence / 'synthesis_sta_summary.txt', content[timing_start:timing_end])
        save(evidence / 'synthesis_resource_summary.txt', '\n'.join(ascii_text(l) for l in lines[:119]) + '\n')
        ddr_timing_rows = [ascii_text(l).strip() for l in lines if re.match(
            rb'\s*ddrphy_sysclk\s+ddrphy_sysclk\s+[-0-9]', l)]
        summaries = {}
        for section in ['Setup', 'Hold', 'Recovery', 'Removal']:
            block = re.search(section + r' Summary\(Slow Corner\):(.*?)^=+', content, re.S | re.M)
            if not block:
                continue
            row = re.search(r'^\s*ddrphy_sysclk\s+ddrphy_sysclk\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(\d+)\s+(\d+)', block[1], re.M)
            assert row, section
            summaries[section.lower()] = {'worst_slack_ns': float(row[1]), 'total_negative_slack_ns': float(row[2]),
                                         'failing_endpoints': int(row[3]), 'total_endpoints': int(row[4])}
        snr_report = {'file': snr.relative_to(HERE).as_posix(), 'sha256': sha(snr),
                      'resources': totals, 'primitive_cell_usage': cells, 'performance_estimates': performance,
                      'ddr_common_clock_timing_summary_rows': ddr_timing_rows,
                      'ddr_common_clock_slow_corner': summaries,
                      'design_summary': re.findall(r'^Design Summary\s*:.*', content, re.M),
                      'not_post_route': True, 'timing_closure_claimed': False}
    endpoint_warnings = [w for s in stages.values() for w in s['new_component_warnings']
                         if 'eligible.addr_end_1' in w['message']]
    report = {
        'status': 'compile_and_synthesis_pass_preliminary_unaccepted' if all(s['pass'] for s in stages.values())
                  else 'pds_stage_failed_preliminary_unaccepted',
        'run_directory': run.relative_to(HERE).as_posix(), 'part': 'PG2L100H-6FBG484', 'top_module': TOP_NAME,
        'candidate_top_sha256': sha(HERE / f'rtl/{TOP_NAME}.v'), 'candidate_pds_sha256': sha(HERE / 'project.pds'),
        'run_project_sha256': sha(project), 'component_binding': bindings, 'stages': stages,
        'selected_top_log_message': ascii_text(selection), 'elaborated_module_count': len(all_elaborated),
        'required_cooperative_modules_elaborated': [ascii_text(name) for name in required],
        'inherited_duplicate_module_count': len(structural['inherited_vendor_ip_duplicate_definitions']),
        'pds_duplicate_handling': 'Registered frozen IP accepted by PDS compile without editing IP source or registration',
        'registered_paths': registrations, 'all_registered_paths_local_and_existing': True,
        'pins': {'historical_prr_pads_retained': structural['historical_prr_pad_count'],
                 'hsst_serial_bits_retained': len(structural['hsst_serial_pins_separate_from_prr']),
                 'top_header_unchanged': True, 'constraint_port_queries': port_queries,
                 'post_route_pin_report_available': False},
        'outputs_without_another_new_instance_consumer': structural['new_outputs_without_another_new_instance_consumer'],
        'output_consumer_note': 'This 31-net structural list includes outputs used by legacy crossbar ports, debug aliases and assertions, plus deliberately retained internal diagnostics. It is not a list of 31 missing connections.',
        'endpoint_warning': {'exact_occurrences': endpoint_warnings, 'accepted': False,
                             'mapped_simulation_pending_in_parent': True},
        'pcie_retirement_contract': {'status': 'pending_parent_new_candidate',
                                     'original_pcie_fifo_source_preserved': True,
                                     'writer_completion_proven': False},
        'synthesis_report': snr_report, 'core_clock_mhz': 131.25, 'core_clock_period_ns': 40 * 16 / 84,
        'protected_files_unchanged': len(before), 'source_hash_guard_files': len(initial),
        'no_pnr_ssh_board_ip_generation': True, 'hardware_or_fps_acceptance_claimed': False,
        'failed_attempt_preserved': 'compile_01/compile_result.json',
        'pending': ['Endpoint eligibility function tie warning requires parent mapped ModelSim validation',
                    'Original PCIe retirement/host writer completion contract remains unproven',
                    'Whole-design mapped simulation, PnR and timing closure have not been performed',
                    'Host runtime DDR exclusivity and lease/generation policy remain external requirements',
                    'No board load, paired host RAW/output comparison or hardware/FPS acceptance'],
    }
    write_json('artifacts/pds_evidence.json', report)
    write_json((evidence / 'protected_final.json').relative_to(HERE).as_posix(), {p: protected[p] for p in before})
    write_json((evidence / 'inputs_final.json').relative_to(HERE).as_posix(), initial)
    print(report['status'])
    for action, data in stages.items():
        print(f"{action}: exit={data['exit_code']} warnings={data['warning_count']}")
    if snr_report:
        print('Resources:', json.dumps(snr_report['resources'], sort_keys=True))
        print('DDR core synthesis estimate:', json.dumps(snr_report['performance_estimates']['ddrphy_sysclk']))


if __name__ == '__main__':
    main()
