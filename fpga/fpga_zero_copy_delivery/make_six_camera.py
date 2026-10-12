"""Byte-preserving independent six-camera candidate; no PDS or board access."""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'integrated'
OUT = ROOT / 'integrated_six'


def replace(raw, old, new, count=1):
    old, new = old.encode('ascii'), new.encode('ascii')
    assert raw.count(old) == count, (old, raw.count(old), count)
    return raw.replace(old, new)


META = '''    output wire [31:0] lease_prev_base, lease_bank0, lease_bank1, lease_sequence,
    output wire [1:0] lease_published,
    output wire lease_writer_idle, lease_pending, lease_flush,
'''
INPUTS = '''input wire [191:0] camera_prev_base, camera_bank0, camera_bank1, camera_sequence,
input wire [11:0] camera_published,
input wire [5:0] camera_writer_idle, camera_pending, camera_flush, camera_dma_idle,
input wire [5:0] camera_cmd_valid, camera_awvalid, camera_wvalid, camera_abort,
'''


def transform(relative, raw):
    if relative == 'source/delivery/delivery_regs.v':
        return (ROOT / 'six_camera/delivery_regs.v').read_bytes()
    if relative == 'source/axi_dma/axi_dma_write.v':
        raw = replace(raw, 'input \t\t\t\trst \t\t\t,',
                      'input \t\t\t\trst \t\t\t,\n    output wire lease_idle,')
        return replace(raw, 'assign m_axi_bready = w_done;', '''assign m_axi_bready = w_done;
// Explicit retirement predicate includes queued/accepted AW, stream W and B.
assign lease_idle = cmd_ready && !trans && !burst_trans && !m_axi_awvalid &&
                    !m_axi_wvalid && !w_done && !data_in_abort && !data_in_last;''')
    if relative == 'source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v':
        raw = replace(raw, 'output                           engine_busy,',
                      'output wire lease_pending,\n    output                           engine_busy,')
        return replace(raw, 'assign engine_busy = (curr_state != IDLE);', '''assign engine_busy = (curr_state != IDLE);
    assign lease_pending = vsync_pending || axi_vsync_rise || (|axi_vsync_ff);''')
    if relative == 'source/ov5640/ov5640_ddr/ov5640_ddr.v':
        raw = replace(raw, 'input          axi_clk        ,', META + '    input          axi_clk        ,')
        raw = replace(raw, 'wire                    w_ping_o;', 'wire                    w_ping_o;\n    wire ctrl_pending;')
        raw = replace(raw, '.engine_busy    (engine_busy    ),',
                      '.lease_pending(ctrl_pending),\n    .engine_busy    (engine_busy    ),')
        return replace(raw, 'endmodule', '''assign lease_prev_base=prev_frame_base;
    assign lease_bank0=cam_data_addr_1;
    assign lease_bank1=cam_data_addr_2;
    assign lease_published=xdma_req;
    assign lease_sequence=dbg_last_cnt;
    assign lease_pending=ctrl_pending || m_vsync;
    assign lease_flush=capture_flush;
    assign lease_writer_idle=!engine_busy && !axi_cmd_valid && (!capture_open || capture_complete || capture_bad);
endmodule''')
    if relative == 'source/ov5640/ov5640_top.v':
        # Port declaration inserted at the uniquely named clock port.
        marker = re.search(rb'    input\s+clk_50m\s*,', raw)
        assert marker
        raw = raw[:marker.start()] + (META + '    input wire capture_hold,\n').encode() + raw[marker.start():]
        raw = replace(raw, '.axi_cam_en     (cam_en    ),', '.axi_cam_en     (cam_en && !capture_hold),')
        return replace(raw, '.prev_frame_base(kf_prev_base),', '''.prev_frame_base(kf_prev_base),
        .lease_prev_base(lease_prev_base),.lease_bank0(lease_bank0),.lease_bank1(lease_bank1),
        .lease_published(lease_published),.lease_sequence(lease_sequence),
        .lease_writer_idle(lease_writer_idle),.lease_pending(lease_pending),.lease_flush(lease_flush),''')
    if relative == 'source/delivery/delivery_top_adapter.v':
        start = raw.index(b'output wire capture_hold,')
        end = raw.index(b'input wire [6:0] s_axi_awid,', start)
        raw = raw[:start] + ('output wire [5:0] capture_hold,\n' + INPUTS).encode() + raw[end:]
        start = raw.index(b'.camera_state(camera_state)')
        end = raw.index(b'.cmd_valid(cmd_valid)', start)
        raw = raw[:start] + b'''.camera_prev_base(camera_prev_base),.camera_bank0(camera_bank0),.camera_bank1(camera_bank1),
.camera_sequence(camera_sequence),.camera_published(camera_published),
.camera_writer_idle(camera_writer_idle),.camera_pending(camera_pending),.camera_flush(camera_flush),
.camera_dma_idle(camera_dma_idle),.camera_cmd_valid(camera_cmd_valid),
.camera_awvalid(camera_awvalid),.camera_wvalid(camera_wvalid),.camera_abort(camera_abort),
''' + raw[end:]
        return raw
    if relative == 'source/top.v':
        declarations = '''wire [5:0] six_hold, six_writer_idle, six_pending, six_flush, six_dma_idle;
wire [191:0] six_prev, six_bank0, six_bank1, six_sequence;
wire [11:0] six_published;
'''
        raw = replace(raw, 'wire delivery_hold;', declarations + 'wire delivery_hold;\nassign delivery_hold=six_hold[4];')
        # The old C5 metadata remains connected for diagnostics/backward reference.
        for i, instance in enumerate(('ov5640_top(', 'cam2_ov5640_top (', 'cam3_ov5640_top (',
                                      'cam4_ov5640_top (', 'cam5_ov5640_ddr (', 'cam6_ov5640_ddr (')):
            ports = f'''
    .lease_prev_base(six_prev[{i*32} +: 32]),.lease_bank0(six_bank0[{i*32} +: 32]),
    .lease_bank1(six_bank1[{i*32} +: 32]),.lease_sequence(six_sequence[{i*32} +: 32]),
    .lease_published(six_published[{i*2} +: 2]),.lease_writer_idle(six_writer_idle[{i}]),
    .lease_pending(six_pending[{i}]),.lease_flush(six_flush[{i}]),
'''
            if i < 4:
                ports += f'    .capture_hold(six_hold[{i}]),\n'
            raw = replace(raw, ') ' + instance, ') ' + instance + ports)
        # Only C6 direct admission changes: C5 retains the existing alias above.
        start = raw.index(b') cam6_ov5640_ddr (')
        before, after = raw[:start], raw[start:]
        after = replace(after, '.axi_cam_en     (1\'b1)', '.axi_cam_en     (!six_hold[5])')
        raw = before + after
        for i, instance in enumerate(('ov5640_axi_dma_write(', 'cam2_axi_dma_write(',
                                      'cam3_axi_dma_write(', 'cam4_axi_dma_write(',
                                      'cam5_axi_dma_write (', 'cam6_axi_dma_write (')):
            raw = replace(raw, instance, instance + f'\n    .lease_idle(six_dma_idle[{i}]),')
        start = raw.index(b'.capture_hold(delivery_hold),.camera_state')
        end = raw.index(b'.s_axi_awid', start)
        cmds = ['cam_cmd_valid'] + [f'cam{i}_cmd_valid' for i in range(2,7)]
        aws = ['ov5640_axi_awvalid'] + [f'cam{i}_axi_awvalid' for i in range(2,7)]
        ws = ['ov5640_axi_wvalid'] + [f'cam{i}_axi_wvalid' for i in range(2,7)]
        aborts = ['cam_dma_abort'] + [f'cam{i}_dma_abort' for i in range(2,7)]
        ports = '''.capture_hold(six_hold),.camera_prev_base(six_prev),.camera_bank0(six_bank0),
.camera_bank1(six_bank1),.camera_sequence(six_sequence),.camera_published(six_published),
.camera_writer_idle(six_writer_idle),.camera_pending(six_pending),.camera_flush(six_flush),
.camera_dma_idle(six_dma_idle),
'''
        for name, values in [('cmd_valid',cmds),('awvalid',aws),('wvalid',ws),('abort',aborts)]:
            ports += f'.camera_{name}({{{",".join(reversed(values))}}}),\n'
        return raw[:start] + ports.encode() + raw[end:]
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    # Snapshot only source/project inputs; never traverse active PDS build output.
    originals = {p: p.read_bytes() for p in (BASE / 'source').rglob('*') if p.is_file()}
    originals[BASE / 'project/project.pds'] = (BASE / 'project/project.pds').read_bytes()
    changes = []
    for p, raw in originals.items():
        relative = p.relative_to(BASE).as_posix()
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        new = transform(relative, raw)
        if relative == 'project/project.pds':
            # Resolve all input references from their original project directory.
            def rebase(m):
                path = (BASE / 'project' / m[2].decode('ascii')).resolve()
                import os
                rel = os.path.relpath(path, OUT / 'project').replace('\\', '/')
                if path.is_relative_to(BASE / 'source'):
                    rel = '../source/' + path.relative_to(BASE / 'source').as_posix()
                return m[1] + rel.encode('ascii') + m[3]
            new = re.sub(rb'(\((?:_file|_ip|_ip_source_item) ")([^"]+)(")', rebase, new)
        target.write_bytes(new)
        if new != raw:
            changes.append({'path':relative,'before':digest(raw),'after':digest(new)})
    for p, raw in originals.items():
        assert p.read_bytes() == raw, f'baseline changed during generation: {p}'
    project = (OUT / 'project/project.pds').read_bytes()
    for ref in re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"]+)"', project):
        assert (OUT / 'project' / ref.decode('ascii')).resolve().exists(), ref
    manifest = {'baseline':str(BASE),'candidate':str(OUT),'changed':changes,
                'baseline_inputs':{str(p.relative_to(BASE)):digest(raw) for p,raw in originals.items()},
                'pds_run':False,'board_access':False}
    (ROOT / 'six_camera_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'Generated {OUT}; {len(changes)} changed inputs; baseline hashes preserved')


if __name__ == '__main__':
    main()
