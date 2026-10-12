"""Finite exclusive tag/motion observation; no capture ARM or lease release."""
import json
import os
import time
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/v7_validation')
scope = {'__name__': 'dma_observer'}
source = (root / 'board_poke.py').read_bytes().split(b'mode = sys.argv[1]')[0]
rows = []
try:
    exec(compile(source, 'board_poke.py', 'exec'), scope)
    raw_rd, raw_wr = scope['rd'], scope['wr']
    operation_count = 0
    def record(direction, address, value=None):
        global operation_count
        operation_count += 1
        (root / 'last_operation.json').write_text(json.dumps({'number': operation_count,
            'direction': direction, 'address': hex(address), 'length': 16,
            'value': value, 'time': time.monotonic()}))
    def rd(address):
        record('F2H', address)
        value = raw_rd(address)
        assert value is not None, 'Nonzero read ioctl result'
        return value
    def wr(address, value):
        record('H2F', address, value)
        scope['TX'][0:16] = bytes(16)
        raw_wr(address, value)
    assert rd(0x20000830) == 0x4d4f5431
    for sample in range(7):
        row = {'sample': sample, 'time': time.monotonic(), 'tags': [], 'motion': []}
        for camera in range(6):
            base = 0x800000 + camera * 0x400000
            row['tags'].append([rd(base + 614400), rd(base + 0x200000 + 614400)])
        for camera in range(4):
            wr(0x20000800, 0x80000000 | camera << 8)
            generation = rd(0x20000820)
            words = []
            for index in range(10):
                wr(0x20000800, camera << 8 | index)
                assert rd(0x20000800) == camera << 8 | index
                words.append(rd(0x20000810))
            assert rd(0x20000820) == generation
            row['motion'].append({'camera': camera + 1, 'generation': generation, 'words': words})
        row['sfp'] = [rd(0x20000120 + index * 16) for index in range(7)]
        rows.append(row)
        print(json.dumps(row), flush=True)
        if sample != 6:
            time.sleep(5)
    assert all(value is not None for row in rows for tags in row['tags'] for value in tags)
    (root / 'camera_observation.json').write_text(json.dumps({'status': 'completed', 'rows': rows}, indent=2))
    scope['TX'].close(); scope['RX'].close(); os.close(scope['FD'])
except BaseException as error:
    (root / 'camera_observation.json').write_text(json.dumps({'status': 'uncertain_buffers_held', 'pid': os.getpid(), 'error': repr(error), 'rows': rows}, indent=2))
    print('Observation fault; keeping FD and buffers for inspection', flush=True)
    while True:
        time.sleep(30)
