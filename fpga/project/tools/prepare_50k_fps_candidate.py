"""Generate byte-preserving isolated 50K frame-tail timing experiment."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/bitstream_final_50k_20261003_033106'
DEST = ROOT / 'project/sim/fps50k_merge'
DEST.mkdir(exist_ok=True)
with zipfile.ZipFile(BASE / 'sources.zip') as z:
    data = z.read('source/rtl/cam2_merge.v')
    original = data
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    def replace(old, new):
        global data
        old = old.replace(b'\n', newline)
        new = new.replace(b'\n', newline)
        assert data.count(old) == 1, old
        data = data.replace(old, new)
    replace(b'    reg  [15:0] a_data_r;',
            b'    // 100 us drain interval before the next SOF, then 1 us VS.\n'
            b'    reg [12:0] frame_gap;\n    reg  [15:0] a_data_r;')
    replace(b'            gap_cnt  <= `UD 2\'d0;',
            b'            frame_gap <= `UD 13\'d0;\n            gap_cnt  <= `UD 2\'d0;')
    start = data.index(b'            S_VSYNC: begin')
    end = data.index(b'            default: state <=', start)
    data = data[:start] + newline.join([
        b'            S_VSYNC: begin',
        b'                c_de <= `UD 1\'b0;',
        b'                c_vs <= `UD (frame_gap >= 13\'d6250);',
        b'                frame_gap <= `UD frame_gap + 13\'d1;',
        b'                if (frame_gap == 13\'d6313) begin',
        b'                    c_vs <= `UD 1\'b0;',
        b'                    frame_gap <= `UD 13\'d0;',
        b'                    pair_cnt <= `UD 13\'d0;',
        b'                    state <= `UD S_WAIT_A;',
        b'                end',
        b'            end', b'']) + data[end:]
    (DEST / 'cam2_merge.v').write_bytes(data)
    (DEST / 'baseline_cam2_merge.v').write_bytes(original)
    for name in ['cmos_8_16bit.v', 'video_async_fifo.v', 'reg_config.v']:
        (DEST / name).write_bytes(z.read('source/rtl/' + name))
tb = (ROOT / 'project/sim/edge50k/tb_merge_rows.sv').read_bytes()
(DEST / 'tb_merge_rows.sv').write_bytes(tb)
run = (ROOT / 'project/sim/edge50k/run.do').read_bytes()
run = run.replace(b'set SRC ../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl', b'set SRC .')
(DEST / 'run.do').write_bytes(run)
(DEST / 'candidate.json').write_text(json.dumps({
    'baseline': str(BASE), 'change': 'frame-tail drain guard only; sensor configuration unchanged',
    'baseline_sha256': hashlib.sha256(original).hexdigest(),
    'candidate_sha256': hashlib.sha256(data).hexdigest(),
    'guard_cycles': 6250, 'clock_hz':62500000,
    'production_modified': False}, indent=2))
print(DEST)
