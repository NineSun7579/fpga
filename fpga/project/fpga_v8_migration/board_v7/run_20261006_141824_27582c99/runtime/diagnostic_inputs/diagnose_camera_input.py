"""Exclusive finite read-only camera diagnosis; retain DMA buffers on errors."""
import json
import os
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
compact = '--compact' in sys.argv
output_name = 'input_compact' if compact else 'input_diagnostics'
scope = {'__name__': 'camera_diagnostics'}
rows = []
fields = {'source_pixels': 0x190, 'cdc_pixels': 0x1a0, 'cdc_drops': 0x1b0,
          'post_filter_pixels': 0x30, 'ddr_errors': 0xa0, 'fault': 0,
          'published': 0xf0, 'state': 0x60, 'handshakes': 0x70,
          'vsync_count': 0x20, 'vsync_width': 0x50, 'enabled': 0x40}
if compact:
    fields = {'source_pixels': 0x190, 'cdc_drops': 0x1b0}
try:
    source = (root / 'board_poke.py').read_bytes().split(b'mode = sys.argv[1]')[0]
    exec(compile(source, 'board_poke.py', 'exec'), scope)
    def rd(address):
        (root / 'diagnostic_last_operation.json').write_text(json.dumps({'direction': 'F2H', 'address': hex(address), 'length': 16}))
        value = scope['rd'](address)
        assert value is not None
        return value
    for sample in range(60 if compact else 30):
        row = {'sample': sample, 'time': time.monotonic(), 'cameras': []}
        for camera in range(2):
            base = 0x20000000 + camera * 0x200
            before = rd(base + 0x1c0)
            values = {name: rd(base + offset) for name, offset in fields.items()}
            after = rd(base + 0x1c0)
            row['cameras'].append({'camera': camera + 1, 'source_sequence_before': before,
                'source_sequence_after': after, 'same_source_window': before == after, **values})
        rows.append(row)
        print(json.dumps(row), flush=True)
        time.sleep(0.05 if compact else 0.2)
    (root / (output_name + '.json')).write_text(json.dumps({'status': 'completed', 'rows': rows}, indent=2))
    scope['TX'].close(); scope['RX'].close(); os.close(scope['FD'])
except BaseException as error:
    (root / (output_name + '.json')).write_text(json.dumps({'status': 'uncertain_buffers_held', 'pid': os.getpid(), 'error': repr(error), 'rows': rows}, indent=2))
    print('Fault: retaining buffers and stopping submissions', flush=True)
    while True:
        time.sleep(30)
