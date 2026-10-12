"""Consolidate actual routed results and explicit audit limitations."""
from pathlib import Path
import collections
import json
import re
import xml.etree.ElementTree as ET
from run_route import HERE, guards, inputs, save, processes
from summarize_route import EVIDENCE, sha

def load(p):
    return json.loads(p.read_bytes())

def main():
    processes('final')
    sta = load(EVIDENCE/'final_sta_summary.json')
    tables = load(EVIDENCE/'final_sta_tables.json')
    route = load(EVIDENCE/'route_summary.json')
    focused = HERE/'focused_route_hold/report_timing/fpga_v8_cooperative_top_v2.rtr'
    s = focused.read_bytes().decode('ascii', 'backslashreplace')
    points = []
    for m in re.finditer(r'(?m)^Startpoint\s*:.*?(?=^Startpoint\s*:|\Z)', s, re.S):
        block = m[0]
        fields = {}
        for name in ['Startpoint', 'Endpoint', 'Path Type', 'Path Group']:
            f = re.search(r'^' + name + r'\s*:\s*(.*)$', block, re.M)
            fields[name] = f[1].strip() if f else None
        slack = re.search(r'Slack \(([^)]+)\)\s+([-0-9.]+)', block)
        fields['slack_ns'] = float(slack[2]) if slack else None
        fields['full_detail'] = block
        points.append(fields)
    assert len(points) == 10 and all(p['slack_ns'] > 0 for p in points)
    write = lambda name, data: (EVIDENCE/name).write_text(json.dumps(data, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    write('inherited_ddr_hold_actual_paths.json', {'report_sha256': sha(focused), 'paths': points,
        'slow_min_ns': min(p['slack_ns'] for p in points if 'slow' in p['Path Type']),
        'fast_min_ns': min(p['slack_ns'] for p in points if 'fast' in p['Path Type']),
        'original_synthesis_10_failing_endpoint_names_fully_exported': False,
        'limitation': 'Synthesis summary reports ten failing endpoints but ordinary details list three. Focused synth export was rejected: Flow-0013, input DB must be PNR phase. All artifacts retained. Actual routed five data pins were bound through exact CONNECT evidence; ten paths means five pins across two corners, not a proven bijection to the ten pre-route endpoints.'})
    resources = route['stage_reports']['place_route']['tables']['pnr_resource_usage']['rows']
    usage = {r['data'][0].strip(): float(r['data'][1]) for r in resources}
    lut = ff = 0
    for r in resources:
        if r['data'][0] in ['Use of CLMA', 'Use of CLMS']:
            for c in r['children']:
                if c['data'][0].strip() == 'LUT': lut += int(c['data'][1])
                if c['data'][0].strip() == 'FF': ff += int(c['data'][1])
    check = {r['data'][0]: int(r['data'][1]) for r in tables['check_timing_summary']['rows']}
    negative = load(EVIDENCE/'all_reported_failing_paths.json')
    core_hold = [{k:v for k,v in p.items() if k != 'full_detail'} for p in negative
                 if p['Path Group'] == 'ddrphy_sysclk' and 'min' in p['Path Type']]
    core = {s['section']+' '+s['corner']: [r for r in s['rows'] if r.get('launch',r.get('clock')) == 'ddrphy_sysclk'][0]
            for s in sta['all_corner_summaries']}
    endpoint = HERE.parent/'component_synthesis/endpoint_netlist_sim_01'
    endpoint_evidence = {name: {'sha256': sha(endpoint/name), 'content': load(endpoint/name)}
                         for name in ['results.json','mapped_vs_oracle.json','mapped_vs_rtl.json']}
    dump = (HERE/'final_export/routed_dump.txt').read_bytes()
    regnames = sorted(set(m.decode('ascii') for m in re.findall(rb'\(INSTANCE (\\prep_regs_u/u_motion_register_bank/[^\s]+)',dump)))
    regcons = [m[0].decode('ascii') for m in re.finditer(rb'(?m)^            \(CONNECT\b.*?^            \)',dump,re.S)
               if b'prep_regs_u/u_motion_register_bank/' in m[0]]
    write('motion_register_consumers.json', {'routed_instances_count':len(regnames), 'routed_instance_names':regnames,
                                            'connection_blocks':regcons,
                                            'scope':'Physical retention/connectivity evidence only; no whole mapped functional regression'})
    old = load(HERE/'protected_before.json')
    current = guards()
    assert old == current and inputs() == load(HERE/'inputs_before.json')
    write('protected_final.json', current)
    assert sta['negative_paths_match_summary_endpoint_total']
    assert all(check[k] == 0 for k in ['loops','latch_loops','latchs','no_clock'])
    hsst = load(EVIDENCE/'hsst_actual_phy_audit.json')
    assert route['pins']['all_electrical_attributes_identical']
    assert hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline']
    baseline = load(HERE/'baseline_reference.json')
    old_pinout = ET.fromstring(baseline['baseline_resources_and_pins']['pnr_pinout_report'])
    old_rows = [[d.text or '' for d in r.findall('data')] for r in old_pinout.findall('row')]
    new_rows = [r['data'] for r in route['stage_reports']['place_route']['tables']['pnr_pinout_report']['rows']]
    assert old_rows == new_rows, 'Actual pinout physical locations changed'
    write('actual_pinout_comparison.json', {'all_pinout_rows_identical':True,'pinout_row_count':len(new_rows),
                                           'headers':route['stage_reports']['place_route']['tables']['pnr_pinout_report']['headers'],
                                           'actual_rows':new_rows,
                                           'scope':'285 generic IO pinout rows including GPIO/DDR. Dedicated HSST evidence is audited separately by hard-site and port connections.'})
    handoff = {'status':'PNR completed successfully; timing NOT closed; no bitgen or board acceptance',
        'pnr_receipt':load(HERE/'pnr_result.json'), 'postformat_binding_review':load(HERE/'source_binding_postformat_review.json'),
        'implementation_seconds':1064.64, 'final_sta':sta, 'core_final_all_corners':core,
        'core_actual_hold_failing_paths':core_hold, 'resources':{'routed_LUT':lut,'routed_FF':ff,'DRM':usage['Use of DRM'],
                                                           'APM':usage['Use of APM'],'IO_PRR':usage['Use of IO'],
                                                           'synthesis_LUT':31251,'synthesis_FF':31535,'synthesis_DRM':72.5,'synthesis_tool_IO':114},
        'check_timing':check, 'pins_112_all_attributes_identical':True, 'hsst_14_connections_and_sites_identical':True,
        'all_actual_pinout_physical_rows_identical':True, 'pinout_rows':len(new_rows),
        'motion_histories':{'count':4,'logical_bits_each':153600,'logical_total_bits':614400,'routed_DRM36K_cells':32,
                           'all_cells_read_first_verified':True,'routed_register_bank_instances':len(regnames)},
        'frozen_sources':{'local_files':712,'inputs':694,'rtl_components':17,'rtl_top':1,'registered_entries':402,
                          'unchanged':True,'six_source_fdc_sha256':route['six_source_fdc_hashes'],
                          'top_sha256':sha(HERE/'rtl/fpga_v8_cooperative_top_v2.v'),
                          'route_db_sha256':sha(HERE/'place_route/fpga_v8_cooperative_top_v2_pnr.adf')},
        'protected_unchanged_files':len(current),'all_existing_v2_and_compile_01_immutable':True,
        'inherited_ddr_hold_comparison':'Existing synth estimate -0.004/TNS -0.040/10 failing endpoints. Exact mapped original data nets now five packed-memory pins: slow minimum +0.827 ns, fast minimum +0.508 ns. Current core violation is motion event FIFO at -0.028/-0.015 ns. Original ten synth endpoint identities not fully exported.',
        'endpoint_component_mapped_evidence':endpoint_evidence,
        'limitations':['Timing NOT closed: slow setup 39; slow hold 336; fast hold 225; slow removal 11 failing endpoints.',
                       '62 input and 71 output ports lack IO delays; 470 unscored paths exported. IO paths remain uncertified.',
                       'Virtual clock clk_150m has no clock loads; PDS warns it is treated as normal port/pin. No clock endpoint is missing a clock.',
                       'Component-only mapped endpoint 654 operations evidence does not establish whole-design equivalence.',
                       'Focused synthesis timing export rejected PNR phase requirement; no guessed command retry. Full exact prior ten endpoint identity limitation is recorded.',
                       'Independent reset epochs, physical camera identity, dynamic allocation, F2H posted-write retirement and host ordering remain external blockers.',
                       'No SSH, IP generation, bitstream generation/load, hardware paired comparison or FPGA FPS certification.'],
        'no_blackbox_warning_lines':not route['warnings']['blackbox_lines'],
        'all_negative_path_details':'evidence/all_reported_failing_paths.json','unscored_io_details':'evidence/unconstrained_io_paths.json'}
    save('parent_handoff.json',handoff)
    print('Actual resources:',handoff['resources'])
    print('Core slow/fast:',core)
    print('CHECK:',check)
    print('All guards:',len(current),'negative paths:',len(negative),'motion register instances:',len(regnames))

if __name__ == '__main__':
    main()
