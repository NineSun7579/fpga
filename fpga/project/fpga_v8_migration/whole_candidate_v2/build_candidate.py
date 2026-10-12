"""Byte-only isolated builder. Never invokes PDS, IP generators, SSH, or board tools."""
from pathlib import Path
import hashlib
import json
import re
import stat
import difflib

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BASE = PROJECT / 'motion_100h/run_20261003_212303'
MIGRATION = HERE.parent
TOP_HASH = 'ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2'
TOP_NAME = 'fpga_v8_cooperative_top_v2'
COMPLETION = HERE / 'artifacts/capture_endpoint_completion.json'
COMPONENTS = [
    'cooperative_core/fpga_v8_cooperative_core.v',
    'cooperative_control/fpga_v8_coop_control_axil.v',
    'cooperative_axi/fpga_v8_raw_frame_axi.v',
    'cooperative_arbiter/fpga_v8_ddr_write_arbiter.v',
    'raw_preprocess/fpga_v8_raw_letterbox.v',
    'raw_preprocess/fpga_v8_rgb888_pack128.v',
    'ddr_adapter_contract/fpga_v8_ddr_adapter.v',
    'capture_lease/fpga_v8_capture_lease.v',
    'capture_lease/fpga_v8_capture_ov5640_ddr.v',
    'cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v',
    'capture_endpoint/fpga_v8_capture_control_axil.v',
    'capture_endpoint/fpga_v8_coop_axil_router.v',
]
ORIGINAL_COMPONENTS = COMPONENTS[:]
COMPONENTS = ['whole_candidate/rtl/' + Path(rel).name for rel in ORIGINAL_COMPONENTS]
COMPONENTS += ['capture_arm_contract/fpga_v8_capture_control_axil_arm_v2.v']
COMPONENTS += ['pcie_h2f_transport_contract/artifacts/' + name + '.v' for name in [
    'fpga_v8_pcie_fifo_h2f', 'fpga_v8_pcie_dma_controller_h2f',
    'fpga_v8_pcie_dma_h2f', 'fpga_v8_pango_pcie_top_h2f']]
ACTIVE_COMPONENTS = [rel for rel in COMPONENTS if Path(rel).stem != 'fpga_v8_capture_control_axil']
OLD = MIGRATION / 'whole_candidate'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path = path.resolve()
    assert path.is_relative_to(HERE), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode('ascii'))


def write_json(name, obj):
    save(HERE / name, json.dumps(obj, indent=2, sort_keys=True) + '\n')


def copy_immutable(src, dst):
    data = src.read_bytes()
    assert dst.resolve().is_relative_to(HERE)
    if dst.exists():
        assert dst.read_bytes() == data, f'Immutable copy differs: {dst}'
    else:
        save(dst, data)
        dst.chmod(stat.S_IREAD)
    return digest(data)


def protected_hashes():
    paths = []
    for directory in ['source', 'ipcore']:
        paths.extend(p for p in (PROJECT / directory).rglob('*') if p.is_file())
    paths.extend(PROJECT.rglob('*.pds'))
    for directory in [OLD, MIGRATION / 'capture_arm_contract',
                      MIGRATION / 'pcie_h2f_transport_contract', BASE]:
        paths.extend(p for p in directory.rglob('*') if p.is_file())
    return {str(p.relative_to(PROJECT)).replace('\\', '/'): digest(p.read_bytes())
            for p in sorted(set(paths)) if not p.resolve().is_relative_to(HERE)}


def uncomment(data):
    return re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', data, flags=re.S)


def balanced(data, start):
    assert data[start:start + 1] == b'('
    depth = 0
    for i in range(start, len(data)):
        if data[i:i + 1] == b'(':
            depth += 1
        elif data[i:i + 1] == b')':
            depth -= 1
            if depth == 0:
                return i + 1
    raise AssertionError('Unbalanced parentheses')


def header(data):
    data = uncomment(data)
    m = re.search(rb'\bmodule\s+(\w+)\s*', data)
    assert m
    pos = m.end()
    if data[pos:pos + 1] == b'#':
        pos = balanced(data, data.index(b'(', pos))
    pos = data.index(b'(', pos)
    return data[pos + 1:balanced(data, pos) - 1]


def ports(data, params=None):
    result = {}
    direction = width = None
    for segment in header(data).split(b','):
        segment = segment.strip()
        m = re.match(rb'(input|output|inout)\s+(?:(?:wire|reg)\s+)?(\[[^]]+\])?\s*(\w+)\s*$', segment)
        if m:
            direction, width, name = m.groups()
        else:
            assert re.fullmatch(rb'\w+', segment), segment
            name = segment
        assert direction
        width = width or b''
        resolved = width.decode('ascii')
        for key, value in (params or {}).items():
            resolved = re.sub(r'\b' + key + r'\b', str(value), resolved)
        if resolved:
            a, z = resolved[1:-1].split(':')
            assert re.fullmatch(r'[0-9+* /()-]+', a + z), resolved
            av = eval(a, {"__builtins__": {}}, {})
            zv = eval(z, {"__builtins__": {}}, {})
            assert int(av) == av and int(zv) == zv
            resolved = f'[{int(av)}:{int(zv)}]'
        result[name.decode('ascii')] = (direction.decode('ascii'), resolved)
    return result


def instance(module, name, connections, params=None):
    param_text = ''
    if params:
        param_text = ' #(\n' + ',\n'.join(f'    .{k}({v})' for k, v in params.items()) + '\n)'
    return module + param_text + ' ' + name + ' (\n' + ',\n'.join(
        f'    .{port}({net})' for port, net in connections.items()) + '\n);\n'


def legacy_main_not_used():
    before = protected_hashes()
    original = (BASE / 'inputs/source/top.v').read_bytes()
    assert digest(original) == TOP_HASH, 'Wrong motion source baseline'
    manifest_bytes = (BASE / 'input_sha256.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest['source/top.v'] == TOP_HASH
    frozen = {}
    for src in sorted((BASE / 'inputs').rglob('*')):
        if src.is_file():
            rel = src.relative_to(BASE / 'inputs').as_posix()
            assert rel in manifest, f'Unmanifested frozen input: {rel}'
            assert digest(src.read_bytes()) == manifest[rel], f'Frozen hash mismatch: {rel}'
            frozen[rel] = copy_immutable(src, HERE / 'inputs' / rel)
    copy_immutable(BASE / 'input_sha256.json', HERE / 'baseline/input_sha256.json')
    copy_immutable(BASE / 'project.pds', HERE / 'baseline/project.pds')
    copy_immutable(BASE / 'pin_audit.json', HERE / 'baseline/pin_audit.json')
    component_hashes = {}
    component_bytes = {}
    for rel in COMPONENTS:
        src = MIGRATION / rel
        assert src.exists(), f'Pending component interface: {rel}'
        name = src.stem
        component_bytes[name] = src.read_bytes()
        component_hashes[rel] = copy_immutable(src, HERE / 'rtl' / src.name)

    top = original
    changes = []

    def edit(label, old, new):
        nonlocal top
        old = old.encode('ascii') if isinstance(old, str) else old
        new = new.encode('ascii') if isinstance(new, str) else new
        assert top.count(old) == 1, (label, top.count(old))
        at = top.index(old)
        changes.append({'label': label, 'line_before_operation': top[:at].count(b'\n') + 1,
                        'old_ascii_escaped': old.decode('ascii', 'backslashreplace'),
                        'new_ascii_escaped': new.decode('ascii', 'backslashreplace'),
                        'old_hex': old.hex(), 'new_hex': new.hex(),
                        'old_sha256': digest(old), 'new_sha256': digest(new)})
        top = top[:at] + new + top[at + len(old):]

    def region(label, start, end, new):
        a = top.index(start)
        z = top.index(end, a)
        edit(label, top[a:z], new)

    edit('Unique top name', b'module top #(', f'module {TOP_NAME} #(')
    # Keep original pin header and all clocks. Remove both old FIFOs and every ID shim.
    region('Remove old DDR FIFOs and read route reconstruction', b'wire [4:0] wr_water_level;',
           b'ddr3 #(', '// Cooperative DDR contract instances are declared below.\n\n')
    region('Retire six-writer arbiter, fabricated BID/B, AW/AR shims', b'ddr_w_arb u_ddr_w_arb (',
           b'/////////////////////////////     DDR3   ///////////////////////////////////////////////////',
           '// Seven-writer cooperative core and DDR adapter instantiated below.\n\n')

    # M00 full request widths must reach the adapter before range checks.
    for net, old_width, new_width in [
        ('ddr_axi_araddr', b'[27:0]', b'[31:0]'),
        ('ddr_axi_arlen', b'[3:0]', b'[7:0]'),
        ('npu_reg_axi_awid', b'[AXI_ID_LEN-1:0]', b'[AXI_ID_M_LEN-1:0]'),
        ('npu_reg_axi_bid', b'[AXI_ID_LEN-1:0]', b'[AXI_ID_M_LEN-1:0]'),
        ('npu_reg_axi_rid', b'[AXI_ID_LEN-1:0]', b'[AXI_ID_M_LEN-1:0]'),
        ('npu_reg_axi_awlen', b'[3:0]', b'[7:0]'),
    ]:
        pattern = rb'(?m)^wire[^;\r\n]*\b' + net.encode() + rb'[^;\r\n]*;'
        matches = list(re.finditer(pattern, top))
        assert len(matches) == 1, (net, matches)
        old = matches[0].group()
        assert old_width in old
        edit('Widen ' + net, old, old.replace(old_width, new_width))
    for net in ['npu_s0_axi_arvalid', 'npu_s0_axi_rready',
                'npu_reg_axi_awready', 'npu_reg_axi_wready', 'npu_reg_axi_bid',
                'npu_reg_axi_bresp', 'npu_reg_axi_bvalid', 'npu_reg_axi_arready',
                'npu_reg_axi_rid', 'npu_reg_axi_rdata', 'npu_reg_axi_rresp',
                'npu_reg_axi_rlast', 'npu_reg_axi_rvalid']:
        matches = list(re.finditer(rb'(?m)^assign\s+' + net.encode() + rb'\s*=.*?;', top))
        assert len(matches) == 1, net
        edit('Remove parked assignment ' + net, matches[0].group(), b'')

    for port, old, new in [
        ('m00_axi_rresp', "2'b00", 'ddr_axi_rresp'),
        ('m00_axi_rvalid', '!ddr_axi_fifo_empty', 'ddr_axi_rvalid'),
        ('s02_axi_arqos', "4'b0", 'v8_read_arqos'),
    ]:
        match = re.search(rb'\.' + port.encode() + rb'\s*\(\s*([^)]*)\)', top)
        assert match, port
        actual = match.group(1).strip().decode('ascii')
        # Frozen S02 uses decimal constants. Accept the known equivalent form only.
        assert actual in [old, "4'd0", "0"], (port, actual)
        edit('Connect ' + port, match.group(), f'.{port}({new})')

    # Every newly inserted instance is mapped from its actual current ANSI API.
    schemas = {name: ports(data, {'DATA_WIDTH': 16, 'AXI_DATA_WIDTH': 128, 'ID_WIDTH': 7})
               for name, data in component_bytes.items() if name in [
                   'fpga_v8_cooperative_core', 'fpga_v8_capture_lease',
                   'fpga_v8_capture_ov5640_ddr', 'fpga_v8_capture_control_axil',
                   'fpga_v8_coop_axil_router', 'fpga_v8_coop_axi128_endpoint',
                   'fpga_v8_ddr_adapter']}
    nets = {}
    all_instances = []
    connections_audit = []

    def declare(net, width):
        if net in nets:
            assert nets[net] == width, (net, nets[net], width)
        else:
            nets[net] = width

    def add(module, inst_name, conn, params=None):
        assert set(conn) == set(schemas[module]), (module, set(schemas[module]) - set(conn))
        for port, (_, width) in schemas[module].items():
            net = conn[port]
            if re.fullmatch(r'v8_\w+', net):
                declare(net, width)
        connections_audit.append({'module': module, 'instance': inst_name,
                                  'parameters': params or {}, 'ports': conn})
        all_instances.append(instance(module, inst_name, conn, params))

    # Physical cam5 stream remains the unchanged sfp_rx_cam_if RGB565 output.
    wrapper = 'fpga_v8_capture_ov5640_ddr'
    old_capture = re.search(rb'ov5640_ddr\s*#\(.*?\)\s*cam5_ov5640_ddr\s*\(.*?\);', top, re.S)
    # Anchor from the exact declaration; a non-greedy match must not start at cam6/another wrapper.
    assert old_capture and b'cam6_ov5640_ddr' not in old_capture.group()
    old_capture_ports = dict((a.decode(), b.strip().decode('ascii')) for a, b in
                             re.findall(rb'\.(\w+)\s*\(([^()]*)\)', old_capture.group().split(b') cam5_ov5640_ddr (', 1)[1]))
    wc = {}
    for port in schemas[wrapper]:
        if port in old_capture_ports:
            wc[port] = old_capture_ports[port]
        elif port in ['epoch_start', 'lease_block', 'admitted_sof', 'capture_bank',
                      'publish', 'publish_seq', 'retired_error', 'engine_idle',
                      'capture_flush_o', 'frame_good_o', 'capture_overflow_o']:
            wc[port] = 'v8_cap_' + port
        else:
            raise AssertionError(('Unmapped wrapper port', port))
    add(wrapper, 'cam5_ov5640_ddr', wc, {'DATA_WIDTH': '16', 'AXI_DATA_WIDTH': '128',
        'CAM_DATA_LEN': '38400', 'BANK0_ADDR': "32'h01800000", 'BANK1_ADDR': "32'h01a00000", 'DEVICE': '"PG"'})
    wrapper_text = all_instances.pop()
    edit('Replace only physical cam5 wrapper; same DMA and RAW wires', old_capture.group(), wrapper_text)

    # Shared core descriptor/release nets are precisely the capture lease API fields.
    lease = 'fpga_v8_capture_lease'
    lc = {port: 'v8_cap_' + port for port in schemas[lease]}
    lc.update(clk='axi_clk', rst='axi_rst')
    add(lease, 'u_v8_capture_lease', lc, {'BANK0_ADDR': "32'h01800000", 'BANK1_ADDR': "32'h01a00000",
        'RAW_LENGTH': '614400', 'CAM_DATA_LEN': '38400', 'FRAME_WIDTH': '640',
        'FRAME_HEIGHT': '480', 'DATA_WIDTH': '16', 'CAM_ID': '4', 'HOST_REQUIRED': '1'})

    core = 'fpga_v8_cooperative_core'
    cc = {}
    cameras = ['ov5640_axi_', 'cam2_axi_', 'cam3_axi_', 'cam4_axi_', 'cam5_axi_', 'cam6_axi_']
    core_desc = {'input_source_seq': 'input_seq', 'input_camera_bank': 'input_bank',
                 'input_lease_token': 'input_token'}
    core_release = {'src_release_camera_bank': 'release_bank', 'src_release_token': 'release_token'}
    for port in schemas[core]:
        if port == 'core_clk':
            cc[port] = 'axi_clk'
        elif port == 'rst_n':
            cc[port] = '~axi_rst'
        elif port.startswith('s_axil_'):
            cc[port] = port.replace('s_axil_', 'v8_c0_')
        elif port.startswith('camera_'):
            suffix = port[len('camera_'):]
            fields = [cam + suffix for cam in cameras]
            if suffix == 'awlen':
                # Frozen cam3/cam4 already expose 8-bit DMA LEN; the others expose 4.
                fields = [field if cameras[i] in ['cam3_axi_', 'cam4_axi_'] else
                          "{4'b0000," + field + '}' for i, field in enumerate(fields)]
            elif suffix in ['awqos', 'awregion']:
                fields = ["4'b0000"] * 6
            cc[port] = '{' + ', '.join(reversed(fields)) + '}'
        elif port.startswith('m_axi_write_'):
            suffix = port[len('m_axi_write_'):]
            cc[port] = ('v8_write_' if suffix in ['awqos', 'awregion'] else 'arb_s_') + suffix
        elif port.startswith('m_axi_read_'):
            suffix = port[len('m_axi_read_'):]
            cc[port] = ('v8_read_' if suffix in ['arlen', 'arqos', 'arregion'] else 'npu_s0_axi_') + suffix
        elif port in core_desc:
            cc[port] = 'v8_cap_' + core_desc[port]
        elif port.startswith('input_') and port not in ['input_claim', 'input_reject']:
            cc[port] = 'v8_cap_' + port
        elif port.startswith('src_release_') and port != 'src_release_addr':
            cc[port] = 'v8_cap_' + core_release.get(port, port.replace('src_', ''))
        else:
            cc[port] = 'v8_coop_' + port
    add(core, 'u_v8_cooperative_core', cc, {'OUTPUT_BANK0_ADDR': "32'h08000000",
        'OUTPUT_BANK1_ADDR': "32'h08200000", 'DDR_ADDRESS_LIMIT': "32'h10000000", 'AXI_ID': "4'd1"})

    control = 'fpga_v8_capture_control_axil'
    ctrl = {port: port.replace('s_axil_', 'v8_c1_') if port.startswith('s_axil_') else 'v8_cap_' + port
            for port in schemas[control]}
    ctrl.update(clk='axi_clk', rst_n='~axi_rst')
    add(control, 'u_v8_capture_control', ctrl, {'LOCAL_BASE': "32'h00000100"})
    router = 'fpga_v8_coop_axil_router'
    rc = {}
    for port in schemas[router]:
        rc[port] = port.replace('s_axil_', 'v8_ep_').replace('m0_axil_', 'v8_c0_').replace('m1_axil_', 'v8_c1_')
    rc.update(clk='axi_clk', rst_n='~axi_rst')
    add(router, 'u_v8_axil_router', rc)
    endpoint = 'fpga_v8_coop_axi128_endpoint'
    ec = {port: port.replace('s_axi_', 'npu_reg_axi_').replace('m_axil_', 'v8_ep_')
          for port in schemas[endpoint]}
    ec.update(clk='axi_clk', rst_n='~axi_rst')
    add(endpoint, 'u_v8_axi128_endpoint', ec, {'ID_WIDTH': 'AXI_ID_M_LEN',
        'BASE_ADDR': "32'h40010000", 'WINDOW_BYTES': "32'h00001000"})
    # Existing M02 had implicit one-bit AR/QoS/region nets. Declare all missing ports.
    for port, net in ec.items():
        if net.startswith('npu_reg_axi_') and not re.search(rb'\bwire\b[^;]*\b' + net.encode() + rb'\b[^;]*;', top):
            declare(net, schemas[endpoint][port][1])

    adapter = 'fpga_v8_ddr_adapter'
    ac = {}
    vendor = {'v_awid': 'ddr3_aw_id', 'v_awaddr': 'ddr3_aw_addr', 'v_awlen': 'ddr3_aw_len',
              'v_awvalid': 'ddr3_aw_v', 'v_awready': 'ddr_axi_awready',
              'v_wdata': 'ddr_axi_wdata_ddr3', 'v_wstrb': 'ddr_axi_wstrb_ddr3',
              'v_wready': 'ddr_axi_wready_ddr3', 'v_wlast': 'ddr_axi_wusero_last_ddr3',
              'v_wid': 'ddr_axi_wusero_id', 'v_arid': 'ddr3_ar_id', 'v_araddr': 'ddr3_ar_addr',
              'v_arlen': 'ddr3_ar_len', 'v_arvalid': 'ddr3_ar_v', 'v_arready': 'ddr_axi_arready',
              'v_rid': 'ddr_axi_rid_ddr3', 'v_rdata': 'ddr_axi_rdata_ddr3',
              'v_rlast': 'ddr_axi_rlast_ddr3', 'v_rvalid': 'ddr_axi_rvalid_ddr3'}
    for port in schemas[adapter]:
        if port in vendor:
            ac[port] = vendor[port]
            if ac[port].startswith('ddr3_'):
                declare(ac[port], schemas[adapter][port][1])
        elif port.startswith('s_a') or port.startswith('s_w') or port.startswith('s_b'):
            if port.startswith('s_ar'):
                suffix = port[2:]
                ac[port] = 'ddr_axi_' + ('aruser_id' if suffix == 'arid' else 'arready_xbar' if suffix == 'arready' else suffix)
            else:
                ac[port] = 'arb_s_' + port[2:]
        elif port.startswith('s_r'):
            ac[port] = 'ddr_axi_' + port[2:]
        elif port == 'read_fifo_empty':
            ac[port] = 'ddr_axi_fifo_empty'
        elif port == 'write_fifo_full':
            ac[port] = 'ddr_axi_fifo_full'
        else:
            ac[port] = 'v8_ddr_' + port
    ac.update(clk='axi_clk', rst_n='~axi_rst')
    declare('ddr_axi_arready_xbar', '')
    declare('ddr3_aw_ap', '')
    declare('ddr3_ar_ap', '')
    add(adapter, 'u_v8_ddr_adapter', ac, {'DDR_ADDRESS_LIMIT': "32'h10000000"})

    extras = '''
// Fixed downstream cam5 binding: 640x480 RGB565, no local filter on this branch.
// Generation allocation and host exclusivity are required external protocol policy.
assign npu_s0_axi_arlen = v8_read_arlen[3:0];
assign ddr3_aw_ap = 1'b0;
assign ddr3_ar_ap = 1'b0;
assign ddr_axi_ruser = 2'b00;
// Preserve the legacy debug aliases without retaining the removed FIFO/ID logic.
assign ddr_axi_awaddr = arb_s_awaddr[27:0];
assign ddr_axi_awlen = arb_s_awlen[3:0];
assign ddr_axi_awvalid = arb_s_awvalid;
assign ddr_axi_awuser_id = {3'b000, arb_s_awid};
assign ddr_axi_awuser_ap = 1'b0;
assign ddr_axi_awsize = arb_s_awsize;
assign ddr_axi_awburst = arb_s_awburst;
assign ddr_axi_awlock = arb_s_awlock;
assign ddr_axi_awcache = arb_s_awcache;
assign ddr_axi_awprot = arb_s_awprot;
assign ddr_axi_awqos = v8_write_awqos;
assign ddr_axi_wdata = arb_s_wdata;
assign ddr_axi_wstrb = arb_s_wstrb;
assign ddr_axi_wvalid = arb_s_wvalid;
assign ddr_axi_wlast = arb_s_wlast;
assign ddr_axi_bvalid = arb_s_bvalid;
assign ddr_axi_bresp = arb_s_bresp;
assign ddr_axi_bid = {3'b000, arb_s_bid};
assign ddr_axi_bready = arb_s_bready;
// synthesis translate_off
initial begin
    if (AXI_ID_LEN != 4 || AXI_ID_M_LEN != 7 || AXI_DATA_LEN != 128 || BURST_LEN != 16)
        $fatal(1, "Whole candidate requires original 4/7-bit IDs, 128-bit data, 16-beat camera DMA");
end
always @(posedge axi_clk) if (!axi_rst) begin
    if (npu_s0_axi_arvalid && v8_read_arlen[7:4] != 0)
        $fatal(1, "Cooperative S02 read LEN cannot be truncated");
    if (ddr_axi_arvalid && (ddr_axi_arlen > 15 || ddr_axi_arsize != 4 || ddr_axi_arburst != 1))
        $fatal(1, "M00 read violates vendor DDR beat/burst contract");
    if (v8_cap_release_valid && v8_coop_src_release_addr !=
            (v8_cap_release_bank ? 32'h01a00000 : 32'h01800000))
        $fatal(1, "Cooperative release address disagrees with capture bank identity");
end
// synthesis translate_on
'''
    declarations = '\n'.join('wire ' + (width + ' ' if width else '') + net + ';' for net, width in sorted(nets.items()))
    integration = '\n// BEGIN ISOLATED V8 COOPERATIVE INTEGRATION\n' + declarations + '\n' + extras + '\n'.join(all_instances) + '\n// END ISOLATED V8 COOPERATIVE INTEGRATION\n'
    edit('Add actual capture manager/core/router/endpoint/DDR adapter wiring', b'\nendmodule', integration + '\nendmodule')
    save(HERE / f'rtl/{TOP_NAME}.v', top)
    patch_lines = difflib.unified_diff(
        original.decode('ascii', 'backslashreplace').splitlines(keepends=True),
        top.decode('ascii', 'backslashreplace').splitlines(keepends=True),
        fromfile='frozen_motion/source/top.v', tofile=f'rtl/{TOP_NAME}.v')
    save(HERE / 'artifacts/top_ascii_review.diff', ''.join(patch_lines))

    pds = (BASE / 'project.pds').read_bytes()
    pds = pds.replace(b'"../source/', b'"inputs/source/').replace(b'"../ipcore/', b'"inputs/ipcore/')
    assert pds.count(b'"inputs/source/top.v" + "top:"') == 1
    # PDS source registration requires the timespec field even for fresh RTL.
    new_entries = ''.join('                (_file "rtl/' + Path(rel).name + '"\n                    (_format verilog)\n                    (_timespec "2026-10-03T21:23:03")\n                )\n' for rel in COMPONENTS)
    new_entries += f'                (_file "rtl/{TOP_NAME}.v" + "{TOP_NAME}:"'
    pds = pds.replace(b'                (_file "inputs/source/top.v" + "top:"', new_entries.encode('ascii'))
    assert pds.count(b'(_option top_module (_string "top"))') == 1
    pds = pds.replace(b'(_option top_module (_string "top"))', f'(_option top_module (_string "{TOP_NAME}"))'.encode())
    assert b'"../' not in pds
    paths = re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', pds)
    assert paths and all((HERE / p.decode('ascii')).is_file() for p in paths)
    assert all((HERE / p.decode('ascii')).resolve().is_relative_to(HERE) for p in paths)
    save(HERE / 'project.pds', pds)

    # Final hashes prove baseline and protected production/IP/PDS did not change.
    after = protected_hashes()
    assert before == after, 'Protected source/IP/PDS mutation detected'
    assert frozen == {rel: digest((BASE / 'inputs' / rel).read_bytes()) for rel in frozen}
    assert TOP_HASH == digest((BASE / 'inputs/source/top.v').read_bytes())
    write_json('artifacts/protected_hashes_before.json', before)
    write_json('artifacts/protected_hashes_after.json', after)
    write_json('artifacts/frozen_copy_sha256.json', frozen)
    write_json('artifacts/component_binding.json', component_hashes)
    write_json('artifacts/connection_manifest.json', connections_audit)
    write_json('artifacts/byte_change_manifest.json', changes)
    write_json('artifacts/build_manifest.json', {
        'status': ('generated_isolated_candidate_compile_released_preliminary'
                   if COMPLETION.exists() else 'generated_isolated_candidate_compile_held_for_capture_endpoint_completion'),
        'baseline': str(BASE), 'baseline_top_sha256': TOP_HASH,
        'baseline_input_manifest_sha256': digest(manifest_bytes),
        'baseline_pds_sha256': digest((BASE / 'project.pds').read_bytes()),
        'frozen_input_count': len(frozen),
        'historical_manifest_non_input_entries': sorted(set(manifest) - set(frozen)),
        'component_count': len(COMPONENTS), 'top_module': TOP_NAME,
        'candidate_top_sha256': digest(top), 'candidate_pds_sha256': digest(pds),
        'pds_local_registered_paths': [p.decode('ascii') for p in paths],
        'no_pds_or_ip_generation_invoked': True, 'no_ssh_or_board_access': True,
        'protected_files_unchanged': len(before),
    })
    state = 'compile released, preliminary only' if COMPLETION.exists() else 'compile held'
    print(f'Generated {TOP_NAME}: {len(frozen)} frozen inputs, {len(COMPONENTS)} component copies; {state}.')


def main():
    assert not (HERE / 'project.pds').exists(), 'Fresh build only; never replace completed sources'
    before = protected_hashes()
    write_json('artifacts/protected_hashes_before.json', before)
    old_build = json.loads((OLD / 'artifacts/build_manifest.json').read_bytes())
    assert old_build['baseline_top_sha256'] == TOP_HASH
    assert digest((BASE / 'inputs/source/top.v').read_bytes()) == TOP_HASH
    frozen = json.loads((OLD / 'artifacts/frozen_copy_sha256.json').read_bytes())
    assert len(frozen) == 694
    for rel, expected in frozen.items():
        assert digest((OLD / 'inputs' / rel).read_bytes()) == expected
        assert digest((BASE / 'inputs' / rel).read_bytes()) == expected
        assert copy_immutable(OLD / 'inputs' / rel, HERE / 'inputs' / rel) == expected
    for src in (OLD / 'baseline').rglob('*'):
        if src.is_file():
            copy_immutable(src, HERE / 'baseline' / src.relative_to(OLD / 'baseline'))
    copy_immutable(OLD / 'rtl/fpga_v8_cooperative_top.v', HERE / 'baseline/firstversion_top.v')
    copy_immutable(OLD / 'project.pds', HERE / 'baseline/firstversion_project.pds')
    for name in ['component_binding.json', 'byte_change_manifest.json', 'build_manifest.json',
                 'connection_manifest.json', 'pds_evidence.json', 'structural_audit.json']:
        copy_immutable(OLD / 'artifacts' / name, HERE / 'baseline' / name)
    arm = json.loads((MIGRATION / 'capture_arm_contract/bindings_manifest.json').read_bytes())
    pcie = json.loads((MIGRATION / 'pcie_h2f_transport_contract/artifacts/edit_manifest.json').read_bytes())
    bindings = {}
    for rel in COMPONENTS:
        src = MIGRATION / rel
        h = copy_immutable(src, HERE / 'rtl' / src.name)
        if rel.startswith('whole_candidate/'):
            prior = next(v for k, v in json.loads((OLD / 'artifacts/component_binding.json').read_bytes()).items()
                         if Path(k).name == src.name)
            assert h == prior
        elif rel.startswith('capture_arm_contract/'):
            assert h == arm['new_source_sha256'][src.name] == 'b65d5cc7a6e0bc1bdf765dfd6da0bb9488cc0ab27d95fe7e6db730170aa857e9'
        else:
            assert h == pcie[src.name]['sha256']
        bindings[rel] = h
    receipts = ['capture_arm_contract/bindings_manifest.json', 'capture_arm_contract/artifacts/review_receipt.json',
                'capture_arm_contract/endpoint/artifacts/results.json',
                'capture_arm_contract/core/artifacts/results.json',
                'capture_arm_contract/core_final_b/artifacts/results.json',
                'pcie_h2f_transport_contract/artifacts/edit_manifest.json',
                'pcie_h2f_transport_contract/artifacts/results.json',
                'pcie_h2f_transport_contract/artifacts/f2h_parity.json']
    for rel in receipts:
        copy_immutable(MIGRATION / rel, HERE / 'baseline/receipts' / rel)
    old_top = (OLD / 'rtl/fpga_v8_cooperative_top.v').read_bytes()
    top = old_top
    changes = json.loads((OLD / 'artifacts/byte_change_manifest.json').read_bytes())
    edits = []
    for label, old, new in [
        ('Unique v2 top', b'module fpga_v8_cooperative_top #(', b'module fpga_v8_cooperative_top_v2 #('),
        ('Capture ARM controller binding only', b'fpga_v8_capture_control_axil #(', b'fpga_v8_capture_control_axil_arm_v2 #('),
        ('PCIe production FIFO chain binding only', b'pcie_fifo #(', b'fpga_v8_pcie_fifo_h2f #(')]:
        assert top.count(old) == 1, (label, top.count(old))
        change = {'label': label, 'line_before_operation': top[:top.index(old)].count(b'\n') + 1,
                  'old_hex': old.hex(), 'new_hex': new.hex(),
                  'old_sha256': digest(old), 'new_sha256': digest(new),
                  'old_ascii_escaped': old.decode(), 'new_ascii_escaped': new.decode()}
        changes.append(change)
        edits.append(change)
        top = top.replace(old, new, 1)
    save(HERE / f'rtl/{TOP_NAME}.v', top)
    for name, source in [('top_ascii_review.diff', (BASE / 'inputs/source/top.v').read_bytes()),
                         ('firstversion_to_v2.diff', old_top)]:
        save(HERE / 'artifacts' / name, ''.join(difflib.unified_diff(
            source.decode('ascii', 'backslashreplace').splitlines(True),
            top.decode('ascii', 'backslashreplace').splitlines(True),
            fromfile='frozen_motion_top' if name.startswith('top_') else 'firstversion_top',
            tofile=f'rtl/{TOP_NAME}.v')))
    connections = json.loads((OLD / 'artifacts/connection_manifest.json').read_bytes())
    for obj in connections:
        if obj['module'] == 'fpga_v8_capture_control_axil':
            obj['module'] = 'fpga_v8_capture_control_axil_arm_v2'
    assert ports((HERE / 'rtl/fpga_v8_capture_control_axil.v').read_bytes()) == ports(
        (HERE / 'rtl/fpga_v8_capture_control_axil_arm_v2.v').read_bytes())
    pds = (OLD / 'project.pds').read_bytes()
    pds = pds.replace(b'fpga_v8_cooperative_top', TOP_NAME.encode())
    pds = pds.replace(b'"rtl/fpga_v8_capture_control_axil.v"', b'"rtl/fpga_v8_capture_control_axil_arm_v2.v"')
    extra = b''.join(('                (_file "rtl/' + Path(rel).name + '"\n'
                    '                    (_format verilog)\n'
                    '                    (_timespec "2026-10-03T21:23:03")\n'
                    '                )\n').encode() for rel in COMPONENTS if rel.startswith('pcie_'))
    anchor = b'                (_file "rtl/' + TOP_NAME.encode() + b'.v"'
    assert pds.count(anchor) == 1
    pds = pds.replace(anchor, extra + anchor, 1)
    paths = re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', pds)
    assert all((HERE / p.decode()).resolve().is_relative_to(HERE) and (HERE / p.decode()).is_file() for p in paths)
    assert not any(b'tests/' in p or b'pcie_shell.sv' in p or b'tb_' in p for p in paths)
    save(HERE / 'project.pds', pds)
    write_json('artifacts/frozen_copy_sha256.json', frozen)
    write_json('artifacts/component_binding.json', bindings)
    write_json('artifacts/connection_manifest.json', connections)
    write_json('artifacts/byte_change_manifest.json', changes)
    write_json('artifacts/v2_byte_change_manifest.json', edits)
    write_json('artifacts/build_manifest.json', {
        'title': '第二版完整隔离候选：ARM 与 PCIe 修正集成',
        'baseline': str(BASE), 'baseline_top_sha256': TOP_HASH,
        'source_base': 'immutable firstversion whole_candidate, frozen ba90 motion; never dca production top',
        'firstversion_top_sha256': digest(old_top), 'frozen_input_count': 694,
        'original_component_snapshots': 12, 'additional_component_snapshots': 5,
        'active_component_count': len(ACTIVE_COMPONENTS), 'top_module': TOP_NAME,
        'candidate_top_sha256': digest(top), 'candidate_pds_sha256': digest(pds),
        'pds_timespec_fix_carried': True, 'default_model_no_explicit_configuration': True,
        'readonly_independent_snapshots': True, 'pds_local_registered_paths': [p.decode() for p in paths],
        'production_source_ip_files': sum(k.startswith(('source/', 'ipcore/')) for k in before),
        'protected_files_unchanged': len(before), 'scope': 'compile and synthesis only; parent review before PnR'})
    write_json('artifacts/capture_endpoint_completion.json', {'status': 'corrected_completed_receipts_hash_verified'})
    after = protected_hashes()
    assert before == after, 'Protected external tree changed'
    write_json('artifacts/protected_hashes_after.json', after)
    print(f'Fresh v2: 694 frozen inputs, 12 original + 5 additional snapshots, {len(ACTIVE_COMPONENTS)} active components.')


if __name__ == '__main__':
    main()
