SRC = 'source/top.v'
raw = open(SRC, 'rb').read()
lines = raw.split(b'\n')

ANCHOR = b'// processed-frame write engine (second write master -> crossbar S03 AW/W/B)'
idx = None
for i, l in enumerate(lines):
    if l.strip() == ANCHOR:
        idx = i
        break
assert idx is not None, 'anchor not found'

BLOCK = [
    b'',
    b'// ===== [2026-09-12] RAW camera path restored =====',
    b'// OptionB commented out cam_prep_link but left cam_s_data undriven, so the',
    b'// camera never wrote DDR -> no frames / no MSI. ov5640_top already emits a',
    b'// complete raw AXI-stream write request, so wire it straight to the raw write',
    b'// engine. The preprocess tap is intentionally NOT used (its TB still fails and',
    b'// its dummy-inject can back-pressure/stall the camera).',
    b'assign cam_s_data         = cam_tap_data;',
    b'assign cam_s_data_valid   = cam_tap_data_valid;',
    b'assign cam_s_data_last    = cam_tap_data_last;',
    b'assign cam_tap_data_ready = cam_s_data_ready;',
    b'',
    b'// preprocess datapath disabled: keep the processed-frame write engine idle',
    b'assign prep_wr_cmd_valid = 1\'b0;',
    b'assign prep_wr_cmd_addr  = 32\'b0;',
    b'assign prep_wr_cmd_len   = 32\'b0;',
    b'assign prep_wr_data      = 128\'b0;',
    b'assign prep_wr_valid     = 1\'b0;',
    b'',
]

out = lines[:idx] + BLOCK + lines[idx:]
open(SRC, 'wb').write(b'\n'.join(out))
print('inserted', len(BLOCK), 'lines at', idx + 1, '; total', len(out))
