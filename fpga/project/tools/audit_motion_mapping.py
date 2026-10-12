"""Audit four local-camera motion histories without running PDS or accepting guesses.

Usage: python project/tools/audit_motion_mapping.py --run RUN --dump RUN/mapped_dump.txt

Only stdout is written. Exit 2 means the resource gate remains unproven. ADIF
scope is CAM1-4 only: four 19200x8 histories, expected 32 DRM36K slices;
CAM5/6 ABI slots are reserved zero and must not have mapped detector histories.
gopDRM parameters, scoped instances and connected ports are extracted; generic
EDIF is recognized but cannot establish Pango primitive semantics. In particular,
physical 32768x1 slices do NOT prove logical 19200x8 geometry. This preparatory
auditor does not emit resource_review.json while geometry and the mapped
enable/comparison schedule lack sufficient evidence. No CLI assertion can
override that requirement. All file hashing operates on original bytes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re
import sys


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+')
HISTORY = re.compile(r'^(.*?/u_detector)/history_(\d+)/(?:gopdrm_36k|gopdrm_18k)$')
CAMERA_PATHS = {
    'CAM1': 'ov5640_top/u_motion_tap/u_detector',
    **{f'CAM{i}': f'cam{i}_ov5640_top/u_motion_tap/u_detector' for i in range(2, 5)},
    **{f'CAM{i}': f'u_cam{i}_motion/u_detector' for i in (5, 6)},
}
EXPECTED = {CAMERA_PATHS[f'CAM{i}'] for i in range(1, 5)}
REQUIRED_HISTORIES = 4
EXPECTED_DRM36K = 32


def decoded(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode('utf-8-sig')
    return raw.decode('gb18030', errors='replace')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(path):
    # Same decoding as build.py evidence checks, preserving original bytes/hash.
    return decoded(path.read_bytes())


def spans(source, tags):
    """Balanced nodes with exact quote offsets; quoted parentheses are harmless.

    Retain only the requested spans instead of constructing a huge netlist AST.
    Unbalanced/truncated vendor output is an error, never partial proof.
    """
    stack = []
    result = defaultdict(list)
    for token in TOKEN.finditer(source):
        value = token.group()
        if value == '(':
            stack.append([token.start(), None])
        elif value == ')':
            if not stack:
                raise ValueError('Unmatched closing parenthesis')
            start, tag = stack.pop()
            if tag in tags:
                result[tag].append((start, token.end()))
        elif stack and stack[-1][1] is None:
            stack[-1][1] = value.upper()
    if stack:
        raise ValueError('Truncated/unbalanced dump')
    return result


def tree(source):
    roots, stack = [], []
    for token in TOKEN.finditer(source):
        value = token.group()
        if value == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif value == ')':
            if not stack:
                raise ValueError('Unmatched node')
            stack.pop()
        else:
            if not stack:
                raise ValueError('Atom outside node')
            stack[-1].append(value)
    if stack or len(roots) != 1:
        raise ValueError('Incomplete node')
    return roots[0]


def children(node, tag):
    return [item for item in node if isinstance(item, list) and item and item[0].upper() == tag]


def descendants(node, tag):
    for item in node:
        if isinstance(item, list) and item:
            if item[0].upper() == tag:
                yield item
            yield from descendants(item, tag)


def name(value):
    if isinstance(value, str):
        return value.strip('"').lstrip('\\')
    if value[0].upper() in ('INDEXED', 'MEMBER'):
        return f'{name(value[1])}[{value[2]}]'
    if value[0].upper() in ('RENAME', 'ARRAY'):
        return name(value[1])
    raise ValueError('Unsupported name form: ' + repr(value))


def parameters(node):
    result = {}
    for item in children(node, 'PARAMETER') + children(node, 'PROPERTY'):
        values = [v for v in item[2:] if isinstance(v, list) and v[0].upper() != 'DATATYPE']
        if len(values) != 1:
            continue
        value = values[0]
        if value[0].upper() in ('STRING', 'INTEGER') and len(value) == 2:
            result[name(item[1])] = value[1].strip('"')
        elif value[0].upper() in ('BITVEC', 'BIT'):
            result[name(item[1])] = value
    return result


@lru_cache(maxsize=8)
def evidence_snapshot(path):
    raw = path.read_bytes()
    return decoded(raw), hashlib.sha256(raw).hexdigest()


def evidence(path, quote, run):
    snapshot, digest = evidence_snapshot(path)
    if not quote or quote not in snapshot:
        raise ValueError('Invalid evidence quote')
    import os
    return {'file': Path(os.path.relpath(path, run)).as_posix(),
            'sha256': digest, 'quote': quote}


def extract(source):
    indexed = spans(source, {'CELL', 'INSTANCE', 'NET'})
    cells, instances, groups = {}, {}, defaultdict(list)
    for start, end in indexed['CELL']:
        quote = source[start:end]
        # Only primitive library cells, not the entire top design CELL.
        if not re.match(r'\(CELL\s+gopDRM(?:\s|_)', quote, re.I):
            continue
        node = tree(quote)
        cells[name(node[1])] = {'parameters': parameters(node), 'quote': quote}
    for start, end in indexed['INSTANCE']:
        quote = source[start:end]
        node = tree(quote)
        inst = name(node[1])
        match = HISTORY.fullmatch(inst)
        if not match:
            continue
        refs = list(descendants(node, 'CELLREF'))
        if len(refs) != 1 or inst in instances:
            raise ValueError('Ambiguous history instance/cell: ' + inst)
        cell = name(refs[0][1])
        inherited = cells.get(cell, {}).get('parameters', {})
        instances[inst] = {'instance': inst, 'cell': cell,
                           'parameters': {**inherited, **parameters(node)},
                           'ports': {}, 'port_quotes': {}, 'quote': quote}
        groups[match[1]].append(inst)
    for start, end in indexed['NET']:
        quote = source[start:end]
        if '/history_' not in quote:
            continue
        node = tree(quote)
        # ADIF ARRAY NET contains one CONNECT/NETREF per bit. The outer ARRAY
        # name alone would collapse all address/data bits onto one false net.
        connections = spans(quote, {'CONNECT'})['CONNECT']
        if not connections:
            raise ValueError('Unsupported NET without CONNECT: ' + name(node[1]))
        for left, right in connections:
            connection_quote = quote[left:right]
            connection = tree(connection_quote)
            netrefs = children(connection, 'NETREF')
            if isinstance(node[1], list) and node[1][0].upper() == 'ARRAY' and len(netrefs) != 1:
                raise ValueError('Array CONNECT requires explicit bit NETREF')
            net = name(netrefs[0][1]) if netrefs else name(node[1])
            for port in descendants(connection, 'PORTREF'):
                refs = children(port, 'INSTREF') + children(port, 'INSTANCEREF')
                if not refs:
                    continue
                inst = name(refs[0][1])
                if inst not in instances:
                    continue
                pin = name(port[1])
                if pin in instances[inst]['ports']:
                    raise ValueError('Duplicate/ambiguous history pin: ' + inst + ':' + pin)
                instances[inst]['ports'][pin] = net
                instances[inst]['port_quotes'][pin] = connection_quote
    return cells, instances, groups


def report_histories(report):
    """Parse pipe table by parent rows, never attribute global utilization."""
    result, current = {}, None
    for line in report.splitlines():
        if not line.startswith('|'):
            continue
        columns = [part.strip() for part in line.split('|')[1:-1]]
        if not columns:
            continue
        detector = columns[0].removesuffix('/history')
        if columns[0].endswith('/history') and detector in CAMERA_PATHS.values():
            current = detector
            # The log contains multiple tables. Preserve each separately.
            result.setdefault(current, []).append({'parent': columns, 'slices': [], 'quotes': [line]})
        elif columns[0] and re.fullmatch(r'history_\d+', columns[0]) and current:
            result[current][-1]['slices'].append(columns)
            result[current][-1]['quotes'].append(line)
        elif columns[0]:
            current = None
    return result


def schedule_summary(detector, items):
    """Concrete pin checks for the observed eight 32Kx1 A0 slices.

    These checks establish shared buses and old-data primitive mode without
    claiming that an opaque enable net computes accept_sample correctly.
    """
    ordered = sorted(items, key=lambda item: int(HISTORY.fullmatch(item['instance'])[2]))
    addresses = [{pin: net for pin, net in item['ports'].items() if pin.startswith('ADA0[')}
                 for item in ordered]
    expected_address = {f'ADA0[{bit}]': f'{detector}/sample_address[{bit}]' for bit in range(15)}
    clocks = [item['ports'].get('CLKA[0]') for item in ordered]
    enables = [(item['ports'].get('CEA[0]'), item['ports'].get('WEA[0]')) for item in ordered]
    indices = [int(HISTORY.fullmatch(item['instance'])[2]) for item in ordered]
    q = [item['ports'].get('QA0[0]') for item in ordered]
    d = [item['ports'].get('DA0[0]') for item in ordered]
    checks = {
        'eight_distinct_bit_slices_0_to_7': indices == list(range(8)),
        'all_15_address_bits_common': bool(addresses) and all(a == addresses[0] and len(a) == 15 for a in addresses),
        'address_bits_are_detector_sample_address': bool(addresses) and all(a == expected_address for a in addresses),
        'all_A0_clocks_axi_clk': bool(clocks) and all(c == 'axi_clk' for c in clocks),
        'CEA0_WEA0_same_nonempty_net_all_slices': bool(enables) and enables[0][0] is not None
            and all(ce == we == enables[0][0] for ce, we in enables),
        'A0_read_before_write_all_slices': bool(ordered) and all(
            item['parameters'].get('CP_WRITE_MODE_A_0') == 'READ_BEFORE_WRITE' for item in ordered),
        'A0_width_one_all_slices': bool(ordered) and all(
            item['parameters'].get('CP_DATA_WIDTH_A_0') == '1' for item in ordered),
        'A0_clock_not_inverted_all_slices': bool(ordered) and all(
            item['parameters'].get('CP_CLKA_OR_POL_INV_0') == 'FALSE' for item in ordered),
        'A0_extra_output_register_disabled_all_slices': bool(ordered) and all(
            item['parameters'].get('CP_OUTPUT_REG_A_0') == 'DISABLE' for item in ordered),
        'QA0_routes_to_history_q_bit_order': indices == list(range(8)) and q == [f'{detector}/history_q[{bit}]' for bit in range(8)],
        'DA0_routes_to_luma_sum_bits_2_to_9': indices == list(range(8)) and d == [f'{detector}/luma_sum[{bit+2}]' for bit in range(8)],
    }
    return {'checks': checks, 'shared_address_bus': addresses[0] if addresses else {},
            'clock_nets': sorted({c for c in clocks if c is not None}),
            'enable_net': enables[0][0] if enables else None,
            'read_output_nets': q, 'write_data_nets': d,
            'primitive_old_data_path_observed': all(checks.values()),
            'remaining': ['Trace shared enable net to rst_n && accept_sample',
                          'Confirm current_q and compare_pending register clock/enable and consumer cycle',
                          'Confirm per-camera elaborated WIDTH/HEIGHT/SAMPLE_STEP and 19200 sample limit']}


def bitvec_integer(value):
    if not isinstance(value, list) or len(value) != 2:
        return None
    radix = value[1]
    if len(radix) == 3 and radix[0] == 'B':
        return int(radix[2].strip('"'), 2)
    return None


def lut_output_table(item, output='L6'):
    """Pango LUT6 scalar uses 64 INIT bits. Dual LUT cells pack L6 in the
    upper 32 and L5 in the lower 32, indexed by I0..I4. Keep that layout visible
    in the report; never apply this decoder to arithmetic/carry operators.
    """
    params = item.get('parameters', {})
    init = bitvec_integer(params.get('INIT'))
    cell = item.get('cell', '')
    if init is None or params.get('MODE') != 'LUT6':
        return None, None, 'unsupported'
    if cell.startswith('gopLUT6_'):
        return init, 6, 'scalar INIT[63:0], index=sum(Ik*2**k)'
    if cell.startswith(('gopLUT6L5_', 'gopLUT6L5Q_', 'gopLUT6QL5_')) and output == 'L6':
        return init >> 32, 5, 'dual LUT L6=INIT[63:32], index=sum(Ik*2**k), k=0..4'
    return None, None, 'unsupported'


def lut_matches(item, required_high, low_or_high=None):
    table, bits, _ = lut_output_table(item)
    if table is None:
        return False
    ports = item.get('ports', {})
    required_pins = []
    for net in required_high:
        pins = [k for k in range(bits) if ports.get(f'I{k}') == net]
        if len(pins) != 1:
            return False
        required_pins.append(pins[0])
    overflow_pin = None
    if low_or_high:
        pins = [k for k in range(bits) if ports.get(f'I{k}') == low_or_high]
        if len(pins) != 1:
            return False
        overflow_pin = pins[0]
    for index in range(1 << bits):
        expected = all((index >> pin) & 1 for pin in required_pins)
        if overflow_pin is not None:
            expected = not expected or bool((index >> overflow_pin) & 1)
        if bool((table >> index) & 1) != expected:
            return False
    return True


def core_source_schedule(raw):
    """Recognize old one-edge consumer and actual registered two-edge decision.
    Return byte quotes; this is source evidence, never future mapped evidence.
    """
    base = [rb'compare_pending <= accept_sample;', rb'if \(accept_sample\) begin\s*current_q <= luma;']
    pipeline = [
        rb'update_pending <= compare_pending;',
        rb'changed_q <= compare_enabled && \(difference >= PIXEL_THRESHOLD\);',
        rb'for \(i = 0; i < TOTAL_BLOCKS; i = i \+ 1\)\s*select_q\[i\] <= \(block_q == i\);',
        rb'update_bx <= bx_q;\s*update_by <= by_q;',
        rb'if \(update_pending && changed_q\) begin',
        rb'if \(select_q\[i\] && block_hits\[i\] < BLOCK_THRESHOLD\)\s*block_hits\[i\] <= block_hits\[i\] \+ 1\x27b1;',
        rb'assign mark_block\[b\] = update_pending && changed_q && select_q\[b\] &&\s*\(block_hits\[b\] == BLOCK_THRESHOLD - 1\);',
        rb'publish_pending <= end_pending;',
    ]
    staged = b'update_pending' in raw
    patterns = base + (pipeline if staged else [rb'if \(compare_pending && compare_enabled && difference >= PIXEL_THRESHOLD\) begin'])
    matches = [re.search(pattern, raw) for pattern in patterns]
    return {'recognized': all(matches), 'work_update_edges_after_sample': 2 if staged else 1,
            'decision_registers': ['update_pending', 'changed_q', 'select_q', 'update_bx', 'update_by'] if staged else [],
            'local_block_counters': staged and all(matches),
            'quotes': [match.group().decode('gb18030') for match in matches if match],
            'mapped_extra_stages_required': staged}


def sfp_source_reset(raw, camera_number):
    cam = f'cam{camera_number}'.encode('ascii')
    stem = cam + b'_motion_reset_sync'
    declaration = re.search(rb'\(\* ASYNC_REG = "TRUE", syn_preserve = 1, syn_keep = 1 \*\) reg \[1:0\] ' + stem + rb';', raw)
    alias = re.search(rb'wire ' + cam + rb'_motion_rst_n = ' + stem + rb'\[1\];', raw)
    chain = re.search(rb'always @\(posedge axi_clk or negedge sfp_motion_rst_n\) begin\s*'
                      rb'if \(!sfp_motion_rst_n\) ' + stem + rb' <= 2\x27b00;\s*'
                      rb'else ' + stem + rb' <= \{' + stem + rb'\[0\], 1\x27b1\};\s*end', raw)
    instance = re.search(rb'motion_stream_adapter\s+u_' + cam + rb'_motion\s*\([^;]+\);', raw)
    connected = bool(instance and re.search(rb'\.rst_n\(' + cam + rb'_motion_rst_n\)', instance.group()))
    present = stem in raw
    return {'kind': 'two_flop_local_release' if present else 'shared_combinational',
            'recognized': bool(declaration and alias and chain and connected) if present else True,
            'mapped_release_net_expected': stem.decode('ascii') + '[1]' if present else None,
            'release_edges': 2 if present else 0,
            'quotes': [match.group().decode('gb18030') for match in (declaration, alias, chain, instance) if match] if present else []}


def logic_witnesses(source, detectors, ram_instances):
    """Collect actual control/register pins, cell parameters and quoted nodes.

    Numeric LUT convention: bit index = sum(Ik * 2**k); printed BITVEC is
    MSB-first. Restrict truth decoding to a plain MODE=LUT6 gopLUT6. Packed
    LUT6QL5 and ARITH INIT layouts are preserved, not treated as plain LUT6.
    """
    indexed = spans(source, {'INSTANCE', 'CELL', 'NET'})
    selected, required_cells = {}, set()
    extra_drivers = set()
    for item in ram_instances.values():
        quote = item['port_quotes'].get('CEA[0]')
        if quote:
            for port in descendants(tree(quote), 'PORTREF'):
                refs = children(port, 'INSTREF')
                if refs and name(port[1]) in ('L6', 'L5', 'Y'):
                    extra_drivers.add(name(refs[0][1]))
    for left, right in indexed['INSTANCE']:
        quote = source[left:right]
        node = tree(quote)
        inst = name(node[1])
        local = any(inst.startswith(detector + '/') for detector in detectors)
        reset_register = re.match(r'cam[56]_motion_reset_sync\[\d+\]/', inst)
        if inst not in extra_drivers and not reset_register and not (local and re.search(
                r'/(?:N63|N78|compare_pending|current_q\[\d+\]|update_pending|changed_q|select_q\[\d+\]|update_bx\[\d+\]|update_by\[\d+\])/', inst)):
            continue
        refs = list(descendants(node, 'CELLREF'))
        if len(refs) != 1:
            continue
        cell = name(refs[0][1])
        selected[inst] = {'cell': cell, 'instance_quote': quote, 'ports': {}, 'net_quotes': []}
        required_cells.add(cell)
    definitions = {}
    for left, right in indexed['CELL']:
        quote = source[left:right]
        header = re.match(r'\(CELL\s+(\S+)', quote)
        if header and name(header[1]) in required_cells:
            node = tree(quote)
            definitions[name(node[1])] = {'parameters': parameters(node), 'cell_quote': quote}
    for left, right in indexed['NET']:
        quote = source[left:right]
        if not any(inst in quote for inst in selected):
            continue
        node = tree(quote)
        for start, end in spans(quote, {'CONNECT'})['CONNECT']:
            connection_quote = quote[start:end]
            connection = tree(connection_quote)
            refs = children(connection, 'NETREF')
            net = name(refs[0][1]) if refs else name(node[1])
            for port in children(connection, 'PORTREF'):
                refs = children(port, 'INSTREF')
                if not refs or name(refs[0][1]) not in selected:
                    continue
                item = selected[name(refs[0][1])]
                item['ports'][name(port[1])] = net
                if len(connection_quote) < 20000 and connection_quote not in item['net_quotes']:
                    item['net_quotes'].append(connection_quote)
    for item in selected.values():
        item.update(definitions.get(item['cell'], {'parameters': {}}))
    return selected


def control_summary(detector, witnesses, source_schedule=None, source_reset=None):
    nodes = {inst: item for inst, item in witnesses.items() if inst.startswith(detector + '/')}
    enable_entry = next(((inst, item) for inst, item in witnesses.items()
                         if item['ports'].get('L6') == detector + '/N63'), None)
    enable = enable_entry[1] if enable_entry else {}
    if enable_entry:
        nodes[enable_entry[0]] = enable
    reset = next((item for inst, item in nodes.items() if '/N78/' in inst), {})
    pending = next((item for inst, item in nodes.items() if '/compare_pending/' in inst), {})
    current = [(inst, item) for inst, item in nodes.items() if '/current_q[' in inst]
    ep, pp = enable.get('ports', {}), pending.get('ports', {})
    params = enable.get('parameters', {})
    init = bitvec_integer(params.get('INIT'))
    expected_inputs = {f'I{k}': net for k, net in enumerate([
        'ddr_init_done', 'sfp_sigdet_sync[1]', 'sfp_status_bits[0]',
        'sfp_status_bits[1]', 'sfp_status_bits[3]', detector + '/accept_sample'])}
    reset_inputs = {**expected_inputs, 'I5': detector.rsplit('/u_detector', 1)[0] + '/overflow_reset'}
    camera = detector not in (CAMERA_PATHS['CAM5'], CAMERA_PATHS['CAM6'])
    ready_nets = ['ddr_init_done'] if camera else list(expected_inputs.values())[:5]
    if source_reset and source_reset.get('kind') == 'two_flop_local_release':
        ready_nets = [source_reset['mapped_release_net_expected']]
        cam = detector.split('/')[0].removeprefix('u_')
        for inst, item in witnesses.items():
            if inst.startswith(cam + '_reset_sync['):
                nodes[inst] = item
    enable_function_matches = lut_matches(enable, [*ready_nets, detector + '/accept_sample'])
    reset_function_matches = lut_matches(reset, ready_nets, detector.rsplit('/u_detector', 1)[0] + '/overflow_reset')
    data_registers_match = len(current) == 8
    for inst, item in current:
        bit = int(re.search(r'current_q\[(\d+)\]', inst)[1])
        data_registers_match &= (item['ports'].get('Y') == f'{detector}/luma_sum[{bit+2}]'
                                and item['ports'].get('Q') == f'{detector}/current_q[{bit}]'
                                and item['parameters'].get('QMUX_SEL') == 'YX')
    checks = {
        'RAM_enable_LUT_truth_table_matches_ready_AND_accept_sample': enable_function_matches,
        'RAM_enable_output_is_N63': ep.get('L6') == detector + '/N63',
        'reset_LUT_truth_table_matches_NOT_ready_OR_overflow_reset': reset_function_matches
            and reset.get('ports', {}).get('L6') == detector + '/N78',
        'accept_sample_and_compare_pending_same_operator_L6_L6Q': pp.get('L6') == detector + '/accept_sample'
            and pp.get('L6Q') == detector + '/compare_pending',
        'compare_pending_clock_axi_clk': pp.get('CLK') == 'axi_clk',
        'compare_pending_register_direct_LUT_rising_no_CE_or_latch': all(
            pending.get('parameters', {}).get(key) == value for key, value in {
                'QMUX_SEL': 'YX', 'CLK_POL': 'FALSE', 'LCE_EN': 'FALSE', 'LATCH_EN': 'FALSE'}.items()),
        'comparison_registers_async_reset_from_N78': pp.get('RS') == detector + '/N78'
            and pending.get('parameters', {}).get('FF_RS') == 'RESET'
            and pending.get('parameters', {}).get('RS_MODE') == 'ASYNC'
            and all(item['ports'].get('RS') == detector + '/N78'
                    and item['parameters'].get('FF_RS') == 'RESET'
                    and item['parameters'].get('RS_MODE') == 'ASYNC' for _, item in current),
        'eight_current_q_registers_clock_axi_clk_enabled_accept_sample': len(current) == 8 and all(
            item['ports'].get('CLK') == 'axi_clk' and item['ports'].get('CE') == detector + '/accept_sample'
            and item['parameters'].get('LCE_EN') == 'TRUE' and item['parameters'].get('CLK_POL') == 'FALSE'
            and item['parameters'].get('LATCH_EN') == 'FALSE' for _, item in current),
        'current_q_comb_Y_is_RAM_write_data_registered_Q_is_comparison_data': data_registers_match,
    }
    if source_reset and source_reset.get('kind') == 'two_flop_local_release':
        cam = detector.split('/')[0].removeprefix('u_')
        release = [(inst, item) for inst, item in nodes.items() if inst.startswith(cam + '_reset_sync[')]
        checks['two_distinct_reset_release_flops_axi_clk_async_reset'] = len(release) == 2 and all(
            item['ports'].get('CLK') == 'axi_clk' and item['parameters'].get('RS_MODE') == 'ASYNC'
            and item['parameters'].get('CLK_POL') == 'FALSE' for _, item in release)
        # Direct D routing varies with packed operators. Preserve actual witnesses
        # and demand the 0->1 chain before claiming mapped synchronized release.
        checks['reset_release_stage0_to_stage1_data_connection'] = any(
            any(net == cam + '_reset_sync[0]' for pin, net in item['ports'].items() if pin.startswith('I'))
            for inst, item in release if '_reset_sync[1]/' in inst)
    if source_schedule and source_schedule.get('mapped_extra_stages_required'):
        for register in source_schedule['decision_registers']:
            stages = [(inst, item) for inst, item in nodes.items() if re.search(r'/' + register + r'(?:\[\d+\])?/', inst)]
            checks[f'{register}_mapped_rising_axi_clk_registers_present'] = bool(stages) and all(
                item['ports'].get('CLK') == 'axi_clk' and item['parameters'].get('CLK_POL') == 'FALSE'
                and item['parameters'].get('LATCH_EN') == 'FALSE'
                and any(pin in item['ports'] for pin in ('Q', 'L6Q', 'L5Q')) for _, item in stages)
        update = next((item for inst, item in nodes.items() if '/update_pending/' in inst), {})
        checks['update_pending_data_connected_compare_pending'] = any(
            net == detector + '/compare_pending' for pin, net in update.get('ports', {}).items() if pin.startswith('I'))
    return {'checks': checks, 'enable_INIT_hex': hex(init) if init is not None else None,
            'enable_inputs': {pin: net for pin, net in ep.items() if re.fullmatch(r'I\d+', pin)},
            'enable_decode_layout': lut_output_table(enable)[2],
            'enable_driver_instance': enable_entry[0] if enable_entry else None,
            'enable_expression': ' & '.join([*ready_nets, 'accept_sample']) if enable_function_matches else None,
            'compare_pending_cell': pending.get('cell'),
            'compare_pending_INIT_hex': hex(bitvec_integer(pending.get('parameters', {}).get('INIT')) or 0),
            'reset_INIT_hex': hex(bitvec_integer(reset.get('parameters', {}).get('INIT')) or 0),
            'register_cycle_observed': all(checks.values()),
            'work_update_edges_after_sample': (source_schedule or {}).get('work_update_edges_after_sample', 1),
            'pipeline_mapping_scope': 'Register presence/clocks and pending data connection; decision/select truth and bit counts still require mapped review' if source_schedule and source_schedule.get('mapped_extra_stages_required') else 'Original comparison consumer',
            'manual_review_nodes': nodes}


def frozen_geometry(run, detector):
    """Resolve frozen SFP defaults or camera wrapper dimensions and widening.

    A compatible 32-bit compiler specialization can corroborate several source
    chains. Its logged instance is retained; it is not six mapped instances.
    """
    result = {'source_chain_verified': False, 'compile_parameter_values_explicit': False,
              'depth': None, 'width': None, 'evidence': []}
    camera = detector not in (CAMERA_PATHS['CAM5'], CAMERA_PATHS['CAM6'])
    inventory = json.loads((run / 'input_sha256.json').read_bytes())
    files = {}
    filenames = ['top.v', 'motion/motion_stream_adapter.v', 'motion/block_motion_detector.v']
    if camera:
        filenames.append('ov5640/ov5640_top.v')
    for filename in filenames:
        path = run / 'inputs/source' / filename
        if sha(path) != inventory.get('source/' + filename):
            raise ValueError('Frozen geometry input hash mismatch: ' + filename)
        files[filename] = (path, path.read_bytes())
    top_path, top = files['top.v']
    adapter_path, adapter = files['motion/motion_stream_adapter.v']
    core_path, core = files['motion/block_motion_detector.v']
    adapter_inst = detector.split('/')[0]
    instance = re.search(rb'motion_stream_adapter\s+' + adapter_inst.encode('ascii') + rb'\s*\([^;]+\);', top)
    wrapper_evidence = []
    wrapper_verified = True
    camera_reset_verified = False
    if camera:
        wrapper_path, wrapper = files['ov5640/ov5640_top.v']
        instance = next((match for match in re.finditer(rb'ov5640_top\s*#\((.*?)\)\s*(\w+)\s*\(', top, re.S)
                         if match.group(2) == adapter_inst.encode('ascii')), None)
        tap = re.search(rb'motion_stream_adapter\s*#\(\.WIDTH\(H_CMOS_DISP\),\s*\.HEIGHT\(V_CMOS_DISP\)\)\s*u_motion_tap\s*\(', wrapper)
        h_default = re.search(rb'parameter\s+H_CMOS_DISP\s*=\s*11\x27d640', wrapper)
        v_default = re.search(rb'parameter\s+V_CMOS_DISP\s*=\s*11\x27d480', wrapper)
        typed_adapter = re.search(rb'parameter integer WIDTH\s*=\s*640,\s*HEIGHT\s*=\s*480', adapter)
        typed_core = re.search(rb'parameter integer WIDTH\s*=\s*640,\s*parameter integer HEIGHT\s*=\s*480', core)
        wrapper_verified = bool(instance and tap and h_default and v_default and typed_adapter and typed_core)
        if instance:
            for parameter, expected in ((b'H_CMOS_DISP', b"11'd640"), (b'V_CMOS_DISP', b"11'd480")):
                override = re.search(rb'\.' + parameter + rb'\s*\(([^)]+)\)', instance.group(1))
                if override and override.group(1).strip() != expected:
                    wrapper_verified = False
        if wrapper_verified:
            wrapper_evidence.extend(evidence(wrapper_path, match.group().decode('gb18030'), run)
                                    for match in (tap, h_default, v_default))
            wrapper_evidence.extend(evidence(path, match.group().decode('gb18030'), run)
                                    for path, match in ((adapter_path, typed_adapter), (core_path, typed_core)))
            end = top.find(b');', instance.end())
            top_ports = top[instance.end():end]
            wrapper_clk = re.search(rb'\.video_clk\s*\(axi_clk\)', top_ports)
            wrapper_rst = re.search(rb'\.video_rst\s*\(axi_rst\)', top_ports)
            tap_end = wrapper.find(b');', tap.end())
            tap_ports = wrapper[tap.end():tap_end]
            tap_clk = re.search(rb'\.clk\s*\(video_clk\)', tap_ports)
            tap_rst = re.search(rb'\.rst_n\s*\(~video_rst\)', tap_ports)
            camera_reset_verified = bool(wrapper_clk and wrapper_rst and tap_clk and tap_rst)
            if camera_reset_verified:
                wrapper_evidence.append(evidence(top_path, top[instance.start():end+2].decode('gb18030'), run))
                wrapper_evidence.append(evidence(wrapper_path, wrapper[tap.start():tap_end+2].decode('gb18030'), run))
    defaults = re.search(rb'parameter\s+(?:integer\s+)?WIDTH\s*=\s*640\s*,\s*HEIGHT\s*=\s*480', adapter)
    step = re.search(rb'parameter\s+(?:integer\s+)?SAMPLE_STEP\s*=\s*4', adapter)
    chain = re.search(rb'block_motion_detector\s*#\(\s*\.WIDTH\(WIDTH\),\s*\.HEIGHT\(HEIGHT\),\s*\.SAMPLE_STEP\(SAMPLE_STEP\),[^;]+\)\s*u_detector\s*\(', adapter)
    formulas = [re.search(pattern, core) for pattern in (
        rb'parameter\s+(?:integer\s+)?SAMPLE_COLS\s*=\s*\(WIDTH \+ SAMPLE_STEP - 1\) / SAMPLE_STEP',
        rb'parameter\s+(?:integer\s+)?SAMPLE_ROWS\s*=\s*\(HEIGHT \+ SAMPLE_STEP - 1\) / SAMPLE_STEP',
        rb'localparam\s+(?:integer\s+)?TOTAL_SAMPLES\s*=\s*SAMPLE_COLS \* SAMPLE_ROWS;',
        rb'reg \[7:0\] history \[0:TOTAL_SAMPLES-1\];',
        rb'if \(accept_sample && sample_address != TOTAL_SAMPLES - 1\)\s*sample_address <= sample_address \+ 1\x27b1;',
    )]
    reset_alias = re.search(rb'assign axi_rst\s*=\s*~ddr_init_done;', top)
    sfp_reset = re.search(rb'wire sfp_motion_rst_n\s*=\s*~axi_rst && sfp_sigdet_sync\[1\] &&\s*sfp_status_bits\[3\] && sfp_status_bits\[1\] && sfp_status_bits\[0\];', top)
    core_reset = re.search(rb'\.rst_n\(rst_n && !overflow_reset\)', adapter)
    fire_guard = re.search(rb'wire fire\s*=[^;]+!overflow && !overflow_reset;', adapter)
    source_reset = sfp_source_reset(top, 5 if detector == CAMERA_PATHS['CAM5'] else 6) if not camera else None
    if source_reset:
        result['SFP_release'] = source_reset
    if instance and defaults and step and chain and all(formulas) and wrapper_verified:
        if re.search(rb'\.(?:SAMPLE_COLS|SAMPLE_ROWS)\s*\(', chain.group()):
            result['remaining'] = ['Derived sample geometry is overridden in adapter']
            return result
        result.update({'source_chain_verified': True, 'depth': 19200, 'width': 8,
                       'WIDTH': 640, 'HEIGHT': 480, 'SAMPLE_STEP': 4,
                       'parameter_width_reason': 'No top overrides; unsized decimal defaults are at least 32 bits; core receives those defaults through named overrides',
                       'arithmetic': 'ceil(640/4) * ceil(480/4) = 160 * 120 = 19200; history byte width is 8',
                       'remaining': []})
        if camera:
            result['parameter_width_reason'] = 'Wrapper dimensions are 11-bit 640/480 literals or defaults; adapter and detector declare WIDTH/HEIGHT as integer, widening overrides to 32 bits before arithmetic'
            result['evidence'].extend(wrapper_evidence)
        for path, matches in ((top_path, [instance]), (adapter_path, [defaults, step, chain]), (core_path, formulas)):
            result['evidence'].extend(evidence(path, match.group().decode('gb18030'), run) for match in matches)
        result['reset_chain_verified'] = bool(reset_alias and core_reset and fire_guard and
                                             (camera_reset_verified if camera else sfp_reset and source_reset['recognized']))
        if result['reset_chain_verified']:
            top_matches = [reset_alias] if camera else [reset_alias, sfp_reset]
            for path, matches in ((top_path, top_matches), (adapter_path, [core_reset, fire_guard])):
                result['evidence'].extend(evidence(path, match.group().decode('gb18030'), run) for match in matches)
            result['reset_reason'] = ('Camera video_clk=axi_clk, video_rst=axi_rst=~ddr_init_done, tap rst_n=~video_rst; '
                                      if camera else 'SFP reset aliases DDR-ready/status inputs; ') + 'fire excludes overflow_reset, so accept_sample cannot be asserted while core reset is asserted'
            if source_reset and source_reset['kind'] == 'two_flop_local_release':
                result['reset_reason'] = 'Distinct preserved per-camera two-flop asynchronous-assert/synchronous-release chain; core additionally excludes overflow_reset'
                result['evidence'].extend(evidence(top_path, quote, run) for quote in source_reset['quotes'])
        compile_log = run / 'compile.log'
        if compile_log.is_file():
            successful = next((line for line in text(compile_log).splitlines()
                               if 'motion_stream_adapter.v successfully.' in line), None)
            if successful:
                result['compile_analysis_corroborated'] = True
                result['evidence'].append(evidence(compile_log, successful, run))
    else:
        result['remaining'] = ['Literal parameter/default/array/address-limit source chain or camera integer widening does not match supported template']
    compile_log = run / 'compile.log'
    if result['source_chain_verified'] and compile_log.is_file():
        log = text(compile_log)
        specialization_rows = []
        for match in re.finditer(r'I: Module instance \{top/([^}]+/u_detector)\} parameter value:', log):
            end = log.find('I:', match.end())
            quote = log[match.start():end if end >= 0 else len(log)].rstrip()
            values = {key: {'bits': int(bits), 'value': int(value, 2)} for key, bits, value in
                      re.findall(r'\b(\w+)\s*=\s*(\d+)\x27b([01]+)', quote)}
            specialization_rows.append((match[1], values, quote))
        expected_values = {'WIDTH': 640, 'HEIGHT': 480, 'SAMPLE_STEP': 4, 'SAMPLE_COLS': 160, 'SAMPLE_ROWS': 120}
        candidates = [entry for entry in specialization_rows if all(
            entry[1].get(key) == {'bits': 32, 'value': value} for key, value in expected_values.items())]
        exact = next((entry for entry in specialization_rows if entry[0] == detector), None)
        selected = exact or (candidates[0] if candidates else None)
        if selected and selected in candidates:
            result.update({'compile_parameter_values_explicit': True,
                           'compile_specialization_path': selected[0],
                           'compile_specialization_reused': selected[0] != detector,
                           'compile_parameters': selected[1]})
            result['evidence'].append(evidence(compile_log, selected[2], run))
        else:
            result['remaining'].append('No compatible 32-bit geometry specialization in compile log')
    return result


def audit(args):
    run, dump = args.run.resolve(), args.dump.resolve()
    work = (args.work or run.parent / 'work').resolve()
    mapped = (args.mapped or work / 'device_map/top_map.adf').resolve()
    synthesized = (args.synthesized or work / 'synthesize/top_syn.adf').resolve()
    requirements = json.loads((run / 'resource_requirements.json').read_bytes())
    proof = {'mapped_sha256': sha(mapped), 'synthesized_sha256': sha(synthesized),
             'required_histories': REQUIRED_HISTORIES, 'bits_per_history': 19200 * 8}
    if any(requirements.get(key) != value for key, value in proof.items()):
        raise ValueError('Actual ADF hashes/requirements do not match four-local scope: '
                         + repr({'required_now': proof, 'recorded_run_requirements': requirements}))
    if run not in dump.parents and work not in dump.parents:
        raise ValueError('Dump outside current run/work evidence roots')
    source = text(dump)
    root = next(TOKEN.finditer(source)).group().upper()
    if root != '(':
        raise ValueError('Expected text ADIF/EDIF, not binary ADF')
    cells, instances, groups = extract(source)
    witnesses = logic_witnesses(source, groups.keys(), instances)
    frozen_core = run / 'inputs/source/motion/block_motion_detector.v'
    source_schedule = core_source_schedule(frozen_core.read_bytes())
    uncertainties = []
    if not re.match(r'\s*\(ADIF\b', source, re.I):
        uncertainties.append('Generic EDIF: Pango primitive semantics not established')
    missing = sorted(EXPECTED - groups.keys())
    extra = sorted(groups.keys() - EXPECTED)
    if missing or extra:
        uncertainties.append(f'Four-local-history attribution failed: missing={missing}, unexpected={extra}')
    # Export logs link the text to the exact binary input; hashes alone cannot.
    export_log = run / 'mapped_dump.log'
    linkage = False
    if export_log.is_file():
        log = text(export_log).replace('\\', '/')
        command = f'.switch_db -input {mapped.as_posix()} -output {dump.as_posix()} successfully.'
        linkage = command in log
    if not linkage:
        uncertainties.append('Export log does not name the supplied ADF location (a renamed work directory requires provenance review); actual supplied ADF hashes match requirements')
    utilization = (args.utilization or work / 'synthesize/apm_drm_lutram_utilization.log').resolve()
    tables = report_histories(text(utilization)) if utilization.is_file() else {}
    if not tables:
        uncertainties.append('Attributed synthesis utilization rows missing')
    total_counts = Counter()
    for item in instances.values():
        kind = {'TRUE': 'DRM36K', 'FALSE': 'DRM18K'}.get(item['parameters'].get('CP_DRM_36K'), 'unknown')
        total_counts[kind] += 1
    if total_counts != Counter({'DRM36K': EXPECTED_DRM36K}):
        uncertainties.append('Four-local history primitive allocation differs from expected 32 DRM36K: ' + repr(dict(total_counts)))
    rows = []
    for detector in sorted(groups):
        primitives, counts, quotes = [], Counter(), []
        for inst in sorted(groups[detector]):
            item = instances[inst]
            params, ports = item['parameters'], item['ports']
            kind = {'TRUE': 'DRM36K', 'FALSE': 'DRM18K'}.get(params.get('CP_DRM_36K'), 'unknown')
            counts[kind] += 1
            # Record actual A-side read-before-write parameters and actual nets.
            # Do not infer timing/enable cones from net names or source comments.
            relevant = {pin: net for pin, net in ports.items()
                         if re.match(r'(CLKA|CEA|WEA|CSA|ADA|DA|QA|RSTA|ORA)', pin)}
            primitives.append({'instance': inst, 'cell': item['cell'], 'type': kind,
                               'parameters': {k: v for k, v in params.items() if not k.startswith('CP_INIT_')},
                               'a_side_ports': relevant,
                               'connected_port_count': len(ports),
                               **({'all_ports': ports} if args.details else {})})
            quotes.append(evidence(dump, item['quote'], run))
            for pin, quote in item['port_quotes'].items():
                if re.match(r'(CEA|WEA|ADA0|QA0|DA0)', pin):
                    ev = evidence(dump, quote, run)
                    if ev not in quotes:
                        quotes.append(ev)
            if item['cell'] in cells:
                cell_quote = cells[item['cell']]['quote']
                for start, end in spans(cell_quote, {'PARAMETER'})['PARAMETER']:
                    parameter_quote = cell_quote[start:end]
                    if re.match(r'\(PARAMETER CP_(?:DRM_36K|DATA_WIDTH_|WRITE_MODE_|OUTPUT_REG_|CLKA_|CLKB_)', parameter_quote):
                        ev = evidence(dump, parameter_quote, run)
                        if ev not in quotes:
                            quotes.append(ev)
            if item['cell'] not in cells or not ports:
                uncertainties.append('Primitive definition/ports missing: ' + inst)
            if params.get('CP_WRITE_MODE_A_0') != 'READ_BEFORE_WRITE':
                uncertainties.append('A0 read-before-write parameter missing: ' + inst)
        synthesis_rows = tables.get(detector, [])
        for table in synthesis_rows:
            if table['slices']:
                quotes.extend(evidence(utilization, quote, run) for quote in table['quotes'])
        schedule = schedule_summary(detector, [instances[inst] for inst in groups[detector]])
        geometry = frozen_geometry(run, detector)
        control = control_summary(detector, witnesses, source_schedule, geometry.get('SFP_release'))
        quotes.extend(ev for ev in geometry['evidence'] if ev not in quotes)
        schedule['remaining'] = []
        for label, checks in (('RAM pins', schedule['checks']), ('control/register', control['checks'])):
            failures = [key for key, passed in checks.items() if not passed]
            if failures:
                schedule['remaining'].append(label + ' checks failed: ' + ', '.join(failures))
        schedule['remaining'].extend(geometry.get('remaining', []))
        if source_schedule['mapped_extra_stages_required']:
            schedule['remaining'].append('New decision pipeline: inspect mapped changed_q/select_q/update coordinates data functions and full bit counts; collected register witnesses do not yet validate those functions')
        if geometry.get('SFP_release', {}).get('kind') == 'two_flop_local_release':
            schedule['remaining'].append('New reset-release chain: inspect mapped stage0 constant-one data function, stage1 transfer function and preserved asynchronous assertion routing')
        if not geometry.get('reset_chain_verified'):
            schedule['remaining'].append('Frozen reset/overflow guard source chain not verified')
        for inst, item in control['manual_review_nodes'].items():
            for quote in [item['instance_quote'], item.get('cell_quote', ''), *item['net_quotes']]:
                if quote:
                    ev = evidence(dump, quote, run)
                    if ev not in quotes:
                        quotes.append(ev)
        rows.append({'instance': detector, 'physical_counts': dict(counts),
                     'logical_depth': geometry.get('depth'), 'logical_width': geometry.get('width'),
                     'mode_proven': schedule['primitive_old_data_path_observed'] and control['register_cycle_observed'] and geometry.get('reset_chain_verified', False) and not schedule['remaining'],
                     'schedule': schedule, 'control': control, 'geometry': geometry,
                     'primitives': primitives, 'synthesis_tables': synthesis_rows, 'evidence': quotes})
        uncertainties.extend(detector + ': ' + gap for gap in schedule['remaining'])
        if not any(len(table['slices']) == len(groups[detector]) and all(
                'READ_BEFORE_WRITE' in values and 'SINGLE_PORT' in values and 'GTP_DRM36K_E1' in values
                for values in table['slices']) for table in synthesis_rows):
            uncertainties.append(detector + ': synthesis slice mode/count does not corroborate observed DRM36K mapping')
    rtl_schedule = {'mapped_equivalence_proven': False}
    archive = run / 'inputs/source/motion/block_motion_detector.v'
    inventory = run / 'input_sha256.json'
    if archive.is_file() and inventory.is_file():
        frozen = json.loads(inventory.read_bytes())
        if sha(archive) != frozen.get('source/motion/block_motion_detector.v'):
            raise ValueError('Archived detector does not match frozen source hash')
        raw = archive.read_bytes()
        schedule = re.search(
            rb'always\s*@\(posedge clk\)\s*begin\s*'
            rb'if\s*\(rst_n && accept_sample\)\s*begin\s*'
            rb'history_q\s*<=\s*history\[sample_address\];\s*'
            rb'history\[sample_address\]\s*<=\s*luma;\s*end\s*end', raw)
        if schedule:
            consumer = core_source_schedule(raw)
            rtl_schedule.update({
                'observed_template': 'Enabled synchronous same-address nonblocking read and write; read sees pre-edge data',
                'evidence': [evidence(archive, schedule.group().decode('gb18030'), run)],
                'comparison_schedule': 'At sample edge RAM QA captures old history and current_q captures new luma; decision uses those registered values at edge+1; work consumes the decision at edge+2' if consumer['mapped_extra_stages_required'] else 'At sample edge RAM QA captures old history and current_q captures new luma; work consumes comparison at edge+1',
                'source_pipeline': consumer,
            })
            if consumer['recognized']:
                rtl_schedule['consumer_schedule_verified'] = True
                rtl_schedule['evidence'].extend(evidence(archive, quote, run) for quote in consumer['quotes'])
            else:
                uncertainties.append('Frozen comparison consumer schedule not recognized')
        else:
            uncertainties.append('Archived RTL synchronous read-first template not recognized')
    else:
        uncertainties.append('Frozen archived RTL evidence unavailable')
    rtl_schedule['mapped_equivalence_proven'] = bool(rows) and all(row['mode_proven'] for row in rows) and rtl_schedule.get('consumer_schedule_verified', False)
    return {'accepted': False, 'review_written': False, 'proof': proof,
            'structural_checks_complete': not uncertainties and rtl_schedule['mapped_equivalence_proven'],
            'review_candidate': {'histories': [
                {'instance': row['instance'], 'depth': row['logical_depth'], 'width': row['logical_width'],
                 'mode': 'read_first' if row['mode_proven'] else None,
                 'bram_instances': [primitive['instance'] for primitive in row['primitives']],
                 'physical_counts': row['physical_counts'], 'evidence': row['evidence']}
                for row in rows]} if not uncertainties and rtl_schedule['mapped_equivalence_proven'] else None,
            'dump_sha256': sha(dump), 'export_linkage_observed': linkage,
            'rtl_schedule': rtl_schedule,
            'expected_camera_paths': {cam: path for cam, path in CAMERA_PATHS.items() if path in EXPECTED},
            'reserved_camera_paths_forbidden': {cam: CAMERA_PATHS[cam] for cam in ('CAM5', 'CAM6')},
            'missing_histories': missing, 'histories': rows,
            'total_attributed_counts': dict(sum((Counter(row['physical_counts']) for row in rows), Counter())),
            'uncertainties': uncertainties}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--mapped', type=Path, help='Exact mapped ADF, e.g. preserved work directory')
    parser.add_argument('--synthesized', type=Path, help='Exact synthesized ADF')
    parser.add_argument('--utilization', type=Path, help='Attributed synthesis RAM utilization log')
    parser.add_argument('--details', action='store_true', help='Include inactive B-side ports too')
    args = parser.parse_args()
    try:
        result = audit(args)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        result = {'accepted': False, 'review_written': False, 'uncertainties': [str(error)]}
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 2


if __name__ == '__main__':
    sys.exit(main())
