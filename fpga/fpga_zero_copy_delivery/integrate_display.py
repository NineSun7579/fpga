"""Byte-preserving extension of baseline delivery controls and shared DDR adapter."""
import re

DISPLAY_FILES = ('display_thumbnail_ddr.v', 'rgb565_display_decimator.v',
                 'display_rgb565_pack128.v')
MEM = [(32, 'araddr', 'output'), (8, 'arlen', 'output'), (3, 'arsize', 'output'),
       (2, 'arburst', 'output'), (1, 'arvalid', 'output'), (1, 'arready', 'input'),
       (128, 'rdata', 'input'), (2, 'rresp', 'input'), (1, 'rlast', 'input'),
       (1, 'rvalid', 'input'), (1, 'rready', 'output'), (32, 'awaddr', 'output'),
       (8, 'awlen', 'output'), (3, 'awsize', 'output'), (2, 'awburst', 'output'),
       (1, 'awvalid', 'output'), (1, 'awready', 'input'), (128, 'wdata', 'output'),
       (16, 'wstrb', 'output'), (1, 'wlast', 'output'), (1, 'wvalid', 'output'),
       (1, 'wready', 'input'), (2, 'bresp', 'input'), (1, 'bvalid', 'input'),
       (1, 'bready', 'output')]


def once(raw, old, new):
    old, new = old.encode('ascii'), new.encode('ascii')
    assert raw.count(old) == 1, old
    return raw.replace(old, new, 1)


def regs(raw):
    raw = once(raw, "parameter [31:0] DEST=32'h0a000000,",
               "parameter [31:0] DEST=32'h0a000000, THUMB_DEST=32'h0a200000,")
    raw = once(raw, 'output reg [31:0] cmd_dst',
               'output reg [31:0] cmd_dst,\n    output reg selected_mode')
    raw = once(raw, 'wire busy=core_busy || cmd_valid;',
               'wire busy=core_busy || cmd_valid;\n    wire [31:0] allowed_dest=selected_mode ? THUMB_DEST : DEST;')
    raw = once(raw, 'cmd_valid<=0; cmd_dst<=DEST;',
               'cmd_valid<=0; cmd_dst<=DEST; selected_mode<=0;')
    raw = once(raw, '// This clone reserves one destination only; no arbitrary DDR writes.',
               '// Immutable per-mode destination; no arbitrary DDR writes.')
    raw = once(raw, "if (busy || w_strb!=4'hf || w_data!=DEST) s_bresp<=2;",
               "if (busy || w_strb!=4'hf || w_data!=allowed_dest) s_bresp<=2;")
    raw = once(raw, '                    default: s_bresp<=2;', '''                    BASE+32'hb0: begin
                        // Lease + busy/quarantine protect ownership of S06/m6.
                        // A mode switch cannot retract an announced AXI request.
                        if (busy || capture_hold || quarantined || w_strb!=4'hf || w_data>1)
                            s_bresp<=2;
                        else begin
                            selected_mode<=w_data[0];
                            cmd_dst<=w_data[0] ? THUMB_DEST : DEST;
                            completed<=0; failed<=0; cycles<=0; last_cycles<=0;
                        end
                    end
                    default: s_bresp<=2;''')
    raw = once(raw, "BASE+32'h60: s_rdata<=WIDTH*OUT_HEIGHT*3;",
               "BASE+32'h60: s_rdata<=selected_mode ? (WIDTH/2)*(HEIGHT/2)*2 : WIDTH*OUT_HEIGHT*3;")
    raw = once(raw, "BASE+32'h90: s_rdata<=jobs_done;", """BASE+32'h90: s_rdata<=jobs_done;
                    BASE+32'ha0: s_rdata<=32'h00000003; // bit0 RGB888, bit1 RGB565 thumbnail
                    BASE+32'hb0: s_rdata<={31'd0,selected_mode};""")
    return raw


def adapter(raw):
    start = raw.index(b'delivery_rgb_ddr #(')
    assert raw.count(b'delivery_rgb_ddr #(') == 1
    raw = raw[:start]
    raw = once(raw, 'wire [31:0] src,dst;', 'wire [31:0] src,dst;\nwire selected_mode;')
    raw = once(raw, '.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src(src),.cmd_dst(dst),',
               '.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_src(src),.cmd_dst(dst),\n.selected_mode(selected_mode),')
    text = '// Mode is fixed throughout the cam5 lease, including fault quarantine.\n'
    for core in ('rgb', 'thumb'):
        text += f'wire {core}_ready, {core}_busy, {core}_done, {core}_error, {core}_config_error;\n'
        for width, name, direction in MEM:
            if direction == 'output':
                text += f'wire {f"[{width-1}:0] " if width > 1 else ""}{core}_{name};\n'
    for name in ('ready', 'done', 'error', 'config_error'):
        dest = 'cmd_ready' if name == 'ready' else name
        text += f'assign {dest}=selected_mode ? thumb_{name} : rgb_{name};\n'
    text += 'assign busy=rgb_busy || thumb_busy;\n'
    for _, name, direction in MEM:
        if direction == 'output':
            text += f'assign m_axi_{name}=selected_mode ? thumb_{name} : rgb_{name};\n'
    for core, module, params, select in (
        ('rgb', 'delivery_rgb_ddr', '.WIDTH(WIDTH),.HEIGHT(HEIGHT),.OUT_HEIGHT(OUT_HEIGHT),.TOP_ROWS(TOP_ROWS)', '!selected_mode'),
        ('thumb', 'display_thumbnail_ddr', '.WIDTH(WIDTH),.HEIGHT(HEIGHT)', 'selected_mode')):
        text += f'{module} #({params}) {core}_core (\n'
        text += f'.clk(clk),.rst_n(!rst),.cmd_valid(cmd_valid && {select}),.cmd_ready({core}_ready),\n'
        text += f'.cmd_src(src),.cmd_dst(dst),.busy({core}_busy),.done({core}_done),\n'
        text += f'.error({core}_error),.config_error({core}_config_error),\n'
        ports = []
        for width, name, direction in MEM:
            # Inactive core receives no ready or response valid. Payload gating
            # also keeps inactive inputs deterministic, without generating work.
            value = f'{core}_{name}' if direction == 'output' else f"({select}) ? m_axi_{name} : {width}'d0"
            ports.append(f'.m_axi_{name}({value})')
        text += ',\n'.join(ports) + '\n);\n'
    text += 'endmodule\n'
    return raw + text.encode('ascii')


def project_entries(project):
    pos = project.index(b'(_input', project.index(b'(_widget wgt_my_design_src')) + len(b'(_input')
    entries = b''.join((f'\n                (_file "../source/display/{name}"\n'
                       '                    (_format verilog)\n'
                       '                    (_timespec "2026-10-09T00:00:00")\n'
                       '                )').encode('ascii')
                       for name in DISPLAY_FILES)
    return project[:pos] + entries + project[pos:]


def validate_endpoint(directory):
    missing = [str(directory / name) for name in DISPLAY_FILES if not (directory / name).is_file()]
    if missing:
        raise RuntimeError('No build-ready generation: real display endpoint sources required: ' + ', '.join(missing))
    raw = (directory / DISPLAY_FILES[0]).read_bytes()
    assert re.search(rb'\bmodule\s+display_thumbnail_ddr\b', raw)
    assert b'm_axi_araddr' in raw and b'm_axi_bready' in raw
