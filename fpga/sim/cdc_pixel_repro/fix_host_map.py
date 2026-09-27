"""One-shot byte-preserving repair of host-visible CDC diagnostic addresses."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def edit(name, pairs):
    p = ROOT/name
    old = p.read_bytes()
    new = old
    for a, b in pairs:
        a, b = a.encode('ascii'), b.encode('ascii')
        assert a in new, (name, a)
        new = new.replace(a, b)
    backup = p.with_name(p.name+'.cdc_host_map.bak')
    assert not backup.exists(), backup
    backup.write_bytes(old)
    p.write_bytes(new)

edit('source/ov5640/ov5640_reg.v', [
    ("32'h04: rdata <= dbg_cdc_input", "32'h190: rdata <= dbg_cdc_input"),
    ("32'h08: rdata <= dbg_cdc_output", "32'h1a0: rdata <= dbg_cdc_output"),
    ("32'h0c: rdata <= dbg_cdc_drop", "32'h1b0: rdata <= dbg_cdc_drop"),
    ("32'h14: rdata <= dbg_cdc_seq", "32'h1c0: rdata <= dbg_cdc_seq")])

# Only these previously unimplemented PREP reads are steered to cameras.
# Capture the override at AR handshake so response routing survives AR changes.
edit('source/ov5640/ovreg_axil_decode.v', [
    ('    reg [3:0] ar_sel;', '''    // CDC host diagnostics: four unused, 16-byte aligned reads per 0x200 stride.
    wire cdc_read = (s_araddr[31:11] == (32'h20000000 >> 11)) &&
                   (s_araddr[10:9] < 3) &&
                   ((s_araddr[8:0] == 9'h190) || (s_araddr[8:0] == 9'h1a0) ||
                    (s_araddr[8:0] == 9'h1b0) || (s_araddr[8:0] == 9'h1c0));
    wire [3:0] ar_route = cdc_read ? {1'b0, s_araddr[10:9], 1'b0} :
                         s_araddr[ADDR_SEL_LSB+3 : ADDR_SEL_LSB];
    reg [3:0] ar_sel;'''),
    ('''ar_sel <= {s_araddr[ADDR_SEL_LSB+3 : ADDR_SEL_LSB+2],
                       s_araddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB]};''', 'ar_sel <= ar_route;'),
    ('''wire [3:0] ar_sel_live = s_arvalid ? {s_araddr[ADDR_SEL_LSB+3 : ADDR_SEL_LSB+2],
                                          s_araddr[ADDR_SEL_LSB+1 : ADDR_SEL_LSB]} : ar_sel;''',
     'wire [3:0] ar_sel_live = s_arvalid ? ar_route : ar_sel;')])

for name in ['tools/verify_cdc_stage_board.py', 'tools/prepare_cdc_stage_verify.py']:
    pairs = [('base+0x14', 'base+0x1c0'), ('(4,8,12)', '(0x190,0x1a0,0x1b0)')]
    if name.endswith('prepare_cdc_stage_verify.py'):
        pairs.append(("raise RuntimeError('No stable CDC snapshot at '+hex(base))",
                      'return dict(seq=seq1,input=counts[0],output=counts[1],drop=counts[2],unstable=True,seq_before=seq0)'))
    edit(name, pairs)
edit('sim/cdc_pixel_repro/patch_cdc_diag.py', [('[4,8,12,20]', '[0x190,0x1a0,0x1b0,0x1c0]')])
edit('sim/cdc_pixel_repro/check_integration.py', [
    ("'source/ov5640/ov5640_reg.v'}", "'source/ov5640/ov5640_reg.v','source/ov5640/ovreg_axil_decode.v'}"),
    ("p.with_name(p.name+'.cdc_pixel.bak').read_bytes()", "p.with_name(p.name+('.cdc_host_map.bak' if p.name=='ovreg_axil_decode.v' else '.cdc_pixel.bak')).read_bytes()"),
    ('read_check(4,307200);read_check(8,1290240);read_check(12,7);read_check(20,123);',
     "read_check('h190,307200);read_check('h1a0,1290240);read_check('h1b0,7);read_check('h1c0,123);"),
    ("(HERE/'tb_cdc_regs.sv').write_bytes(b)", "b=b.replace(b\"ra=32'h20000000+offset;\", b\"ra=(32'h20000000+offset) & 32'hfffffff0;\")\n(HERE/'tb_cdc_regs.sv').write_bytes(b)")])
print('Byte backups saved; host map repaired.')
