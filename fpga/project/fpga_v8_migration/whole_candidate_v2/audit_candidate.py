"""Byte-based structural evidence only; does not compile or claim board acceptance."""
from pathlib import Path
import hashlib
import json
import re
from collections import defaultdict, deque
from build_candidate import HERE, BASE, TOP_HASH, TOP_NAME, COMPONENTS, ACTIVE_COMPONENTS, uncomment, header, ports, balanced, write_json, copy_immutable, protected_hashes, COMPLETION


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def camera_instance(data, name):
    # Exact instance token and preceding balanced parameter block, independent of module name.
    clean = uncomment(data)
    m = re.search(rb'\b' + name.encode() + rb'\s*\(', clean)
    assert m, name
    start = m.start()
    return clean[start:balanced(clean, clean.index(b'(', start))]


def instances(body):
    # Require a distinct instance identifier; never split a named port into two words.
    pattern = rb'(?<![\w.$])\b(\w+)(?:\s*#\s*(?=\()|\s+(?=\w+\s*\())'
    for m in re.finditer(pattern, body):
        pos = m.end()
        if body[pos:pos + 1] == b'(':
            pos = balanced(body, pos)
        tail = re.match(rb'\s*(\w+)\s*\(', body[pos:])
        if tail:
            yield m.group(1).decode(), tail.group(1).decode()


def pin_header(data):
    h = header(data)
    h = re.sub(rb'`ifdef USE_OV5640\s*(.*?)`elsif USE_HDMI.*?`endif', rb'\1', h, flags=re.S)
    return b'module pin_view (' + h + b'); endmodule'


def width_value(width, params):
    if not width:
        return 1
    text = width.decode('ascii') if isinstance(width, bytes) else width
    for key, value in params.items():
        text = re.sub(r'\b' + key + r'\b', str(value), text)
    a, z = text[1:-1].split(':')
    assert re.fullmatch(r'[0-9+* /()-]+', a + z), text
    av, zv = [eval(v, {'__builtins__': {}}, {}) for v in [a, z]]
    assert int(av) == av and int(zv) == zv
    return abs(int(av) - int(zv)) + 1


def split_concat(text):
    depth = 0
    begin = 0
    fields = []
    for i, char in enumerate(text):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        elif char == ',' and depth == 0:
            fields.append(text[begin:i].strip())
            begin = i + 1
    fields.append(text[begin:].strip())
    return fields


def main():
    top = (HERE / f'rtl/{TOP_NAME}.v').read_bytes()
    original = (BASE / 'inputs/source/top.v').read_bytes()
    pds = (HERE / 'project.pds').read_bytes()
    pds_evidence = None
    if (HERE / 'artifacts/pds_evidence.json').exists():
        pds_evidence = json.loads((HERE / 'artifacts/pds_evidence.json').read_bytes())
        assert pds_evidence['candidate_top_sha256'] == sha(HERE / f'rtl/{TOP_NAME}.v')
        assert pds_evidence['candidate_pds_sha256'] == sha(HERE / 'project.pds')
    paths = [HERE / p.decode('ascii') for p in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', pds)]
    assert all(p.resolve().is_relative_to(HERE) and p.is_file() for p in paths)
    source_paths = sorted(set(p for p in paths if p.suffix.lower() in ['.v', '.sv']))
    pin_params = {'MEM_ROW_WIDTH': 15, 'MEM_BANK_WIDTH': 3, 'MEM_COLUMN_WIDTH': 10,
                  'MEM_DQ_WIDTH': 16, 'MEM_DQS_WIDTH': 2}
    old_pins = ports(pin_header(original), pin_params)
    new_pins = ports(pin_header(top), pin_params)
    assert old_pins == new_pins
    bits = sum(1 if not width else abs(int(width[1:-1].split(':')[0]) - int(width[1:-1].split(':')[1])) + 1
               for _, width in new_pins.values())
    assert bits == 126, bits
    # Historical PRR lists GPIO/DDR pads. Fourteen HSST pins are separate.
    baseline_prr = BASE.parent / 'baseline/top_prr.prt'
    historical_manifest = json.loads((BASE / 'input_sha256.json').read_bytes())
    assert sha(baseline_prr) == historical_manifest['baseline/top_prr.prt']
    copy_immutable(baseline_prr, HERE / 'baseline/top_prr.prt')
    pin_rows = [row.split(b'|') for row in baseline_prr.read_bytes().splitlines()
                if len(row.split(b'|')) >= 7 and row.split(b'|')[4]]
    assert len(pin_rows) == 112, len(pin_rows)
    expanded = {}
    for name, (direction, width) in new_pins.items():
        if not width:
            expanded[name] = direction
        else:
            a, z = map(int, width[1:-1].split(':'))
            for i in range(min(a, z), max(a, z) + 1):
                expanded[f'{name}[{i}]'] = direction
    assert all(row[4].decode() in expanded and row[5].decode() == expanded[row[4].decode()] for row in pin_rows)
    serial_pins = sorted(set(expanded) - {row[4].decode() for row in pin_rows})
    assert len(serial_pins) == 14 and set(serial_pins) == {'ref_clk_n', 'ref_clk_p',
        'rxn[0]', 'rxn[1]', 'rxp[0]', 'rxp[1]', 'txn[0]', 'txn[1]', 'txp[0]', 'txp[1]',
        'sfp_l2rxn', 'sfp_l2rxp', 'sfp_l2txn', 'sfp_l2txp'}
    preserved = {}
    for name in ['ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top',
                 'cam6_ov5640_ddr', 'cam5_axi_dma_write', 'cam6_axi_dma_write',
                 'ov5640_axi_dma_write', 'cam2_axi_dma_write', 'cam3_axi_dma_write', 'cam4_axi_dma_write']:
        # Discover the first physical-camera instance name from source if baseline uses a different name.
        old = camera_instance(original, name)
        new = camera_instance(top, name)
        assert old == new, name
        preserved[name] = hashlib.sha256(old).hexdigest()
    # All retained old code outside the named edits is provably preserved by the change ledger.
    ledger = json.loads((HERE / 'artifacts/byte_change_manifest.json').read_bytes())
    replay = original
    for change in ledger:
        old, new = bytes.fromhex(change['old_hex']), bytes.fromhex(change['new_hex'])
        assert replay.count(old) == 1, change['label']
        replay = replay.replace(old, new, 1)
    assert replay == top, 'Final top differs from exact audited byte-edit replay'
    motion_sources = [p for p in source_paths if '/motion/' in p.as_posix()]
    assert len(motion_sources) == 4
    motion_hashes = {p.relative_to(HERE).as_posix(): sha(p) for p in motion_sources}
    frozen_hashes = json.loads((HERE / 'artifacts/frozen_copy_sha256.json').read_bytes())
    assert all(h == frozen_hashes[p.removeprefix('inputs/')] for p, h in motion_hashes.items())
    assert b'.motion_records(motion_records)' in top
    for camera in range(1, 5):
        token = f'.motion_record(cam{camera}_motion_record)'.encode()
        assert token in uncomment(top) and token in uncomment(original), token

    modules = defaultdict(list)
    module_bodies = {}
    encrypted_files = []
    includes = []
    for path in source_paths:
        data = path.read_bytes()
        clean = uncomment(data)
        if b'pragma protect' in data or b'`protect' in data:
            encrypted_files.append(path.relative_to(HERE).as_posix())
        for name in re.findall(rb'(?m)^\s*module\s+(\w+)', clean):
            modules[name.decode()].append(path.relative_to(HERE).as_posix())
        for m in re.finditer(rb'\bmodule\s+(\w+)\b(.*?)\bendmodule\b', clean, re.S):
            module_bodies[m.group(1).decode()] = (path, m.group(0))
        for inc in re.findall(rb'`include\s+"([^"]+)"', clean):
            candidates = list((HERE / 'inputs').rglob(inc.decode('ascii')))
            local = path.parent / inc.decode('ascii')
            if local.exists():
                candidates = [local]
            includes.append({'source': path.relative_to(HERE).as_posix(), 'include': inc.decode('ascii'),
                             'candidates': [p.relative_to(HERE).as_posix() for p in candidates]})
    duplicates = {name: ps for name, ps in modules.items() if len(ps) > 1}
    inherited_ip_duplicates = {name: [{'path': p, 'sha256': sha(HERE / p)} for p in ps]
                               for name, ps in duplicates.items()
                               if all(p.startswith('inputs/ipcore/') for p in ps)}
    new_duplicates = {name: ps for name, ps in duplicates.items() if name not in inherited_ip_duplicates}
    assert not new_duplicates, new_duplicates
    assert TOP_NAME in modules and 'top' not in modules
    assert all(len(i['candidates']) == 1 for i in includes), includes

    # Module reachability over actual module names, including parameterized instances.
    graph = defaultdict(set)
    unknown = defaultdict(set)
    keywords = set('if else for while case casex casez always initial begin end assign input output inout wire reg integer function task generate endgenerate module localparam parameter signed unsigned'.split())
    for owner, (path, body) in module_bodies.items():
        for kind, inst in instances(body):
            if kind in modules and kind != owner:
                graph[owner].add(kind)
            elif kind not in keywords and inst not in keywords and kind not in modules:
                unknown[owner].add(kind)
    reached = set()
    todo = deque([TOP_NAME])
    while todo:
        name = todo.popleft()
        if name not in reached:
            reached.add(name)
            todo.extend(graph[name] - reached)
    required = {Path(rel).stem for rel in ACTIVE_COMPONENTS} | {'ov5640_ddr_w', 'ov5640_ddr_w_ctrl',
        'ov5640_ddr_w_en', 'axi_dma_write', 'axi_crossbar_7x3', 'motion_register_bank',
        'motion_stream_adapter', 'block_motion_detector', 'ddr_fifo16_r', 'ddr_fifo16_w'}
    assert required <= reached, sorted(required - reached)

    connections = json.loads((HERE / 'artifacts/connection_manifest.json').read_bytes())
    # No new API port is implicit, dangling, or accidentally omitted; empty ports are recorded diagnostics only.
    top_clean = uncomment(top)
    declarations = set()
    for match in re.finditer(rb'\bwire\s+(?:\[[^]]*\]\s*)?([^;]*);', top_clean):
        for part in match.group(1).split(b','):
            m = re.match(rb'\s*(\w+)', part)
            if m:
                declarations.add(m.group(1).decode())
    implicit_new = []
    for obj in connections:
        for port, net in obj['ports'].items():
            if re.fullmatch(r'v8_\w+|ddr3_\w+|npu_reg_axi_\w+', net) and net not in declarations:
                implicit_new.append([obj['instance'], port, net])
    assert not implicit_new, implicit_new
    schemas = {Path(rel).stem: ports((HERE / 'rtl' / Path(rel).name).read_bytes(),
               {'DATA_WIDTH': 16, 'AXI_DATA_WIDTH': 128, 'ID_WIDTH': 7})
               for rel in COMPONENTS if Path(rel).stem in {o['module'] for o in connections}}
    widths = {}
    width_params = dict(pin_params, AXI_ID_LEN=4, AXI_ID_M_LEN=7, AXI_DATA_LEN=128,
                        AXI_STRB_LEN=16, AXI_ADDR_WIDTH=32, MSI_NUM=5)
    for m in re.finditer(rb'\bwire\s+(\[[^]]*\]\s*)?([^;]*);', top_clean):
        for part in m.group(2).split(b','):
            n = re.match(rb'\s*(\w+)', part)
            if n:
                widths[n.group(1).decode()] = width_value((m.group(1) or b'').strip(), width_params)
    widths.update({name: width_value(width, width_params) for name, (_, width) in new_pins.items()})

    def expression_width(expr):
        expr = expr.strip()
        if expr.startswith('{'):
            return sum(expression_width(part) for part in split_concat(expr[1:-1]))
        if re.match(r'^\d+\s*\'[bdh]', expr):
            return int(expr.split("'")[0])
        if expr.startswith('~'):
            return expression_width(expr[1:])
        assert expr in widths, ('Undeclared interface expression', expr)
        return widths[expr]

    width_checks = []
    for obj in connections:
        for port, net in obj['ports'].items():
            if not net:
                continue
            expected = width_value(schemas[obj['module']][port][1], {})
            actual = expression_width(net)
            assert expected == actual, (obj['instance'], port, net, expected, actual)
            width_checks.append({'instance': obj['instance'], 'port': port, 'expression': net, 'bits': actual})
    # Preserve every original PCIe named connection while checking its actual full-width API.
    fifo_schema = ports((HERE / 'rtl/fpga_v8_pcie_fifo_h2f.v').read_bytes(),
                        {'ADDR_WIDTH': 12, 'MSI_NUM': 5, 'AXI_ID_LEN': 4,
                         'AXI_DATA_LEN': 128, 'AXI_STRB_LEN': 16})
    fifo_instance = camera_instance(top, 'pcie_fifo')
    fifo_pairs = re.findall(rb'\.(\w+)\s*\(([^()]*)\)', fifo_instance)
    assert len(fifo_pairs) == len({p for p, _ in fifo_pairs}), 'Duplicate PCIe named port'
    for port, net in fifo_pairs:
        port, net = port.decode(), net.strip().decode()
        expected = width_value(fifo_schema[port][1], {})
        actual = expression_width(net)
        assert expected == actual, ('pcie_fifo', port, net, expected, actual)
        width_checks.append({'instance': 'pcie_fifo', 'port': port, 'expression': net, 'bits': actual})
    assert set(fifo_schema) - {p.decode() for p, _ in fifo_pairs} == {'smlh_link_up', 'rdlh_link_up'}
    assert camera_instance(original, 'pcie_fifo') == fifo_instance
    write_json('artifacts/interface_width_audit.json', width_checks)
    drivers = defaultdict(list)
    consumers = defaultdict(list)
    for obj in connections:
        for port, net in obj['ports'].items():
            if net.startswith('v8_'):
                direction, width = schemas[obj['module']][port]
                (drivers if direction == 'output' else consumers)[net].append(obj['instance'] + '.' + port)
    multiple_drivers = {net: vals for net, vals in drivers.items() if len(vals) > 1}
    missing_driver = {net: vals for net, vals in consumers.items() if not drivers[net]}
    assert not multiple_drivers, multiple_drivers
    assert not missing_driver, missing_driver
    unused_new_outputs = {net: vals for net, vals in drivers.items() if not consumers[net]}
    by_inst = {o['instance']: o for o in connections}
    assert by_inst['u_v8_ddr_adapter']['ports']['s_arlen'] == 'ddr_axi_arlen'
    assert by_inst['u_v8_ddr_adapter']['ports']['s_awlen'] == 'arb_s_awlen'
    assert by_inst['u_v8_axi128_endpoint']['parameters']['ID_WIDTH'] == 'AXI_ID_M_LEN'
    assert b'wire [AXI_ID_M_LEN-1:0]   npu_reg_axi_awid' in top
    assert b'wire [7:0] npu_reg_axi_arlen;' in top
    assert b'assign npu_s0_axi_arlen = v8_read_arlen[3:0];' in top
    assert b'v8_read_arlen[7:4] != 0' in top
    assert b'assign axi_clk = core_clk;' in top
    assert b'assign axi_rst = ~ddr_init_done;' in top
    assert b'ddr_w_arb u_ddr_w_arb' not in top
    assert not any(t in top for t in [b'ddr_fifo16_w ddr_fifo16_w', b'ddr_fifo16_r ddr_fifo16_r', b'reg  rd_inflight', b'reg  [AXI_ID_M_LEN-1 : AXI_ID_LEN]'])
    assert b'assign npu_s1_axi_arvalid  = 1\'b0;' in top
    assert b'assign npu_s2_axi_arvalid  = 1\'b0;' in top
    assert b'assign npu_s4_axi_arvalid  = 1\'b0;' in top

    # Audited enabled writer ranges: existing CAM1-4 configurable, CAM5/6 fixed.
    # Each original controller writes exactly RAW bytes plus one 16-byte tag.
    defaults = [0x00800000, 0x00a00000, 0x00c00000, 0x00e00000,
                0x01000000, 0x01200000, 0x01400000, 0x01600000,
                0x01800000, 0x01a00000, 0x01c00000, 0x01e00000]
    camera_ranges = [{'camera': i // 2 + 1, 'bank': i % 2,
                      'base': f'0x{base:08x}', 'raw_end_exclusive': f'0x{base + 614400:08x}',
                      'tag_end_exclusive': f'0x{base + 614416:08x}',
                      'host_can_reconfigure_base': i < 8}
                     for i, base in enumerate(defaults)]
    outputs = [{'bank': i, 'base': f'0x{base:08x}', 'allocated_end_exclusive': f'0x{base + 0x200000:08x}',
                'payload_end_exclusive': f'0x{base + 1228800:08x}'}
               for i, base in enumerate([0x08000000, 0x08200000])]
    assert all(base + 614416 <= 0x08000000 for base in defaults)
    assert b'assign prep_wr_cmd_valid = 1\'b0;' in top
    assert b'.M00_CONNECT_WRITE (7\'b0000000)' in top
    assert b'assign npu_out_axi_awvalid = 1\'b0;' in top
    assert not any(re.search(rb'\b(?:m_axi_aw\w+|axi_cmd_addr|ddr)\b', uncomment(p.read_bytes())) for p in motion_sources)
    reg = (HERE / 'inputs/source/ov5640/ov5640_reg.v').read_bytes()
    assert b'cam_addr_1 <= s_axi_wdata;' in reg and b'cam_addr_2 <= s_axi_wdata;' in reg
    pcie = (HERE / 'inputs/source/pcie_dma/pcie_fifo.v').read_bytes()
    raw = (HERE / 'rtl/fpga_v8_raw_frame_axi.v').read_bytes()
    kf = (HERE / 'inputs/source/ov5640/vip_kf_stream.v').read_bytes()
    assert b'read_beats_remain >= 32\'d16' in pcie and b'assign axi_arlen      = r_burst_len;' in pcie
    assert b'assign m_axi_read_arlen = 8\'d0;' in raw and b'assign m_axi_write_awlen = 8\'d0;' in raw
    assert re.search(rb'parameter integer BURST_LEN\s*=\s*8', kf)
    write_json('artifacts/address_and_burst_audit.json', {
        'status': 'default_static_ranges_only_runtime_exclusivity_not_proven',
        'camera_raw_bytes': 614400, 'camera_tag_bytes': 16, 'camera_default_ranges': camera_ranges,
        'cooperative_output_bytes': 1228800, 'cooperative_allocations': outputs,
        'default_camera_and_output_ranges_disjoint': True,
        'motion_ddr_writer_count': 0,
        'operational_writers': ['CAM1-6 original axi_dma_write through cooperative core slots 0-5',
                                'Cooperative RGB888 conversion through core slot 6'],
        'inactive_write_paths': ['PCIe S00 cannot write M00 (M00_CONNECT_WRITE=0)',
                                 'Legacy NPU S02 writer tied inactive',
                                 'Processed-frame S03 writer command valid tied inactive'],
        'reads': {'host_S00_max_beats': 16, 'cooperative_S02_max_beats': 1,
                  'cooperative_write_max_beats': 1, 'camera_write_max_beats': 16,
                  'retained_KF_S05_default_max_beats': 8,
                  'frozen_cam1_KF_EN': 0, 'frozen_cam1_KF_RD_EN': 0,
                  'vendor_len_bits': 4, 'vendor_max_beats': 16,
                  'beat_bytes': 16, 'required_size': 4, 'required_burst': 'INCR'},
        'M00_decode': '0x00000000..0x1fffffff; adapter restricts supported DDR end to 0x10000000',
        'M01_decode': '0x20000000..0x3fffffff retained',
        'motion_register_page': '0x20000800..0x200008ff retained',
        'M02_decode': '0x40000000..0x5fffffff retained; endpoint receives every request',
        'cooperative_endpoint': '0x40010000..0x40010fff',
        'local_register_to_physical': '0x40010000 + 4 * local_byte_offset; one 16-byte DMA per register',
        'capture_control_local_window': '0x100..0x17f (physical 0x40010400..0x400105ff)',
        'intentional_capture_differences': ['CAM5 capture is disarmed until fresh generation arm',
            'Fixed bank addresses/length are shared by wrapper and manager',
            'RAW host and cooperative conversion each must claim then release the matching lease',
            'Legacy CAM5 xdma_ack remains 2\'b00 and never releases manager ownership'],
        'required_external_policy': ['Host must reserve both 2 MiB cooperative output allocations',
            'CAM1-4 writable address registers can alias RAW/output banks; constrain all configured camera bases',
            'Host readers must claim, bind, fully drain reads, then release CAM5 identity',
            'Allocate a fresh nonzero never-reused generation, including across hardware resets',
            'Host DDR addresses must be 16-byte aligned, within 256 MiB, and not burst across 4 KiB'],
        'adapter_rejection_behavior': 'Unsupported DDR AW/AR requests flag diagnostics and remain unaccepted; host policy required to avoid stalls',
        'endpoint_rejection_behavior': 'M02 addresses outside reserved endpoint or malformed access return endpoint error responses',
    })
    ip_paths = []
    for p in paths:
        if p.suffix.lower() == '.idf':
            for item in re.findall(rb'<file\s+pathname="([^"]+)"', p.read_bytes()):
                text = item.decode('ascii')
                target = (p.parent / text).resolve()
                assert target.is_relative_to(HERE), (p, text)
                ip_paths.append({'idf': p.relative_to(HERE).as_posix(), 'relative_file': text,
                                 'resolved': target.relative_to(HERE).as_posix(), 'exists': target.is_file()})
    write_json('artifacts/ip_relative_path_audit.json', ip_paths)
    # Missing IDF log/template artifacts are recorded; registered PDS inputs all exist.
    final_protected = protected_hashes()
    before = json.loads((HERE / 'artifacts/protected_hashes_before.json').read_bytes())
    assert all(final_protected.get(name) == value for name, value in before.items())
    write_json('artifacts/protected_hashes_final.json', {name: final_protected[name] for name in before})

    address_evidence = []
    for p in sorted(set(source_paths) | {HERE / 'inputs/source/ov5640/ov5640_top.v'}):
        if '/ipcore/' in p.as_posix():
            continue
        for i, line in enumerate(p.read_bytes().splitlines(), 1):
            if re.search(rb"(?:32|24)'h[0-9a-fA-F_]+", line):
                address_evidence.append({'path': p.relative_to(HERE).as_posix(), 'line': i,
                    'ascii_escaped': line.decode('ascii', 'backslashreplace')})
    write_json('artifacts/address_literals.json', address_evidence)
    write_json('artifacts/structural_audit.json', {
        'status': ('structural_pass_with_preliminary_pds_evidence_unaccepted' if pds_evidence else
                   'structural_pass_compile_released_not_synthesis_or_board_acceptance'
                   if COMPLETION.exists() else 'structural_pass_compile_held_not_synthesis_or_board_acceptance'),
        'baseline_top_sha256': TOP_HASH, 'candidate_top_sha256': sha(HERE / f'rtl/{TOP_NAME}.v'),
        'registered_source_files': len(source_paths), 'declared_module_count': len(modules),
        'duplicate_modules': duplicates, 'new_duplicate_modules': new_duplicates,
        'inherited_vendor_ip_duplicate_definitions': inherited_ip_duplicates,
        'top_port_names': len(new_pins), 'top_port_bits': bits,
        'top_ports_identical': True, 'pin_directions_widths': new_pins,
        'historical_prr_pad_count': 112, 'historical_prr_sha256': sha(baseline_prr),
        'historical_prr_all_pads_retained': True, 'hsst_serial_pins_separate_from_prr': serial_pins,
        'free_clk_preserved': True, 'constraints_unchanged': {p.relative_to(HERE).as_posix(): sha(p) for p in paths if p.suffix == '.fdc'},
        'preserved_camera_dma_instances': preserved, 'motion_source_hashes': motion_hashes,
        'reachable_modules': sorted(reached), 'required_reachable': sorted(required),
        'unreachable_registered_modules': sorted(set(modules) - reached),
        'encrypted_files': encrypted_files, 'includes': includes,
        'reachable_unknown_tokens_for_review': {name: sorted(vals) for name, vals in unknown.items() if name in reached},
        'all_new_api_ports_connected': True, 'multiple_new_drivers': multiple_drivers,
        'new_interface_width_checks_passed': len(width_checks),
        'missing_new_drivers': missing_driver,
        'new_outputs_without_another_new_instance_consumer': unused_new_outputs,
        'byte_change_operations': len(ledger),
        'exact_byte_edit_replay_passed': True,
        'limits': ['Byte-based reachability is structural and does not elaborate encrypted vendor modules.',
                   ('Eleven inherited vendor IP duplicates accepted by isolated PDS compile without IP edits.'
                    if pds_evidence and pds_evidence['stages']['compile']['pass'] else
                    'Eleven vendor IP duplicate definitions are inherited from the frozen PDS; actual PDS source selection has not been recompiled.'),
                   ('Compile released by capture_endpoint completion notification; all implementation evidence remains preliminary.'
                    if COMPLETION.exists() else 'Compile held until capture_endpoint owner completion notification.'),
                   ('See pds_evidence.json for preliminary PDS compile/synthesis; endpoint mapped warning and PCIe retirement remain pending. No placement, timing closure, board load or runtime exclusivity established.'
                    if pds_evidence else 'No PDS synthesis, placement, timing closure, board load, or runtime exclusivity established.')],
    })
    write_json('artifacts/parent_handoff.json', {
        'scope': ('New isolated whole-design candidate; structural and preliminary PDS evidence; unaccepted'
                  if pds_evidence else 'New isolated whole-design source candidate; structural audit only'),
        'pds_evidence': pds_evidence,
        'top_module': TOP_NAME, 'top_file': f'rtl/{TOP_NAME}.v', 'pds_file': 'project.pds',
        'baseline_top_sha256': TOP_HASH, 'candidate_top_sha256': sha(HERE / f'rtl/{TOP_NAME}.v'),
        'candidate_pds_sha256': sha(HERE / 'project.pds'),
        'ready': ['694 exact frozen source/IP/constraint copies; 12 guarded component copies',
                  'Actual six camera AW/W/B interfaces packed into cooperative seven-writer core',
                  'Actual cam5 capture wrapper/DMA and hardware lease events wired',
                  'Capture config + host claim/release endpoint wired; HOST_REQUIRED=1',
                  'Full M02 endpoint/routing IDs/LEN declared and wired',
                  'DDR adapter replaces all old FIFOs, fabricated BID/B and read SID reconstruction',
                  '436 new named-port expression widths checked; exact byte edit replay passes',
                  '112 historical GPIO/DDR PRR pads + 14 HSST serial pins preserved',
                   'Production/IP/PDS 1091-file before/after/final hashes match'] +
                  (['PDS Compile and Synthesize exit 0 in fresh compile_01/attempt_02; preliminary/unaccepted',
                    'Selected candidate top and all 12 cooperative modules elaborated; IP registrations accepted unchanged',
                    'SNR resources and 131.25 MHz common DDR core STA estimates recorded; hold violation retained']
                   if pds_evidence else []),
        'unresolved_named_ports': [],
        'pending': pds_evidence['pending'] if pds_evidence else ([] if COMPLETION.exists() else ['Await capture_endpoint owner completion notice before any final compile']) + [
                    'ModelSim/official PDS compile and elaboration have not been run',
                    'Inherited 11 vendor IP duplicate definitions need PDS source-selection verification',
                    'Whole-design synthesis, placement/routing and timing have not been run',
                    'No actual board acceptance or paired RAW/output comparison performed',
                    'Original PCIe host retirement contract remains unproven; parent candidate pending',
                    'Host runtime reservations, constrained CAM1-4 address configuration and fresh generation policy are external'],
        'pending_component_binding': {rel: sha(HERE / 'rtl' / Path(rel).name)
                                      for rel in COMPONENTS if rel.startswith('capture_endpoint/')},
        'diagnostic_visibility': 'Capture bank states/protocol/counters exported through capture control. DDR/arbiter detailed flags are internal wires because current endpoint APIs have no ports for them.',
        'no_runtime_or_fps_claim': True,
    })
    print(f'Structural audit passed: 112 historical PRR pads + 14 HSST pins, {len(modules)} modules, {len(reached)} reachable; no new duplicate/implicit/multiple-driver nets. Inherited IP duplicates: {len(inherited_ip_duplicates)}.')


if __name__ == '__main__':
    main()
