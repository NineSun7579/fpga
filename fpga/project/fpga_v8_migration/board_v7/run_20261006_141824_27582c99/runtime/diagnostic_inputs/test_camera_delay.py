"""Single-session CAM1 delay A/B/A trial; hold buffers on uncertain completion."""
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time

root = Path(sys.argv[1])
steps = [int(value) for value in sys.argv[2].split(',')] if len(sys.argv) > 2 else [140, 40, 140]
assert all(0 <= step <= 255 for step in steps) and steps[-1] == 140
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 120
name = sys.argv[4] if len(sys.argv) > 4 else 'delay_trial'
scope = {'__name__': 'delay_trial'}
doc = {'status': 'running', 'stages': [], 'pid': os.getpid()}
def save():
    (root / (name + '.json')).write_text(json.dumps(doc, indent=2))

try:
    source = (root / 'board_poke.py').read_bytes().split(b'mode = sys.argv[1]')[0]
    exec(compile(source, 'board_poke.py', 'exec'), scope)
    def rd(address):
        (root / 'delay_last_operation.json').write_text(json.dumps({'direction': 'F2H', 'address': hex(address), 'length': 16}))
        value = scope['rd'](address)
        assert value is not None, 'Nonzero read result'
        return value
    def wr(address, value):
        (root / 'delay_last_operation.json').write_text(json.dumps({'direction': 'H2F', 'address': hex(address), 'length': 16, 'value': value}))
        scope['TX'][0:16] = struct.pack('<IIII', value, 0, 0, 0)
        operation = scope['O']()
        operation.ddr = address
        operation.ln = 16
        signal.alarm(8)
        try:
            result = scope['fcntl'].ioctl(scope['FD'], scope['I'](4), operation, True)
            assert result == 0, 'Nonzero write result'
        finally:
            signal.alarm(0)
    def counters(base):
        return {'short_overflow': rd(base + 0xa0), 'published': rd(base + 0xf0),
                'source_sequence': rd(base + 0x1c0), 'fault': rd(base)}
    assert rd(0x40010000) == 0x434f4f50
    assert rd(0x400101b0) == 0
    for step in steps:
        wr(0x20000030, step)
        time.sleep(2)
        stage = {'step': step, 'started': time.monotonic(),
                 'before': [counters(0x20000000 + camera * 0x200) for camera in range(2)], 'rows': []}
        doc['stages'].append(stage)
        save()
        for sample in range(samples):
            row = []
            for camera in range(2):
                base = 0x20000000 + camera * 0x200
                before = rd(base + 0x1c0)
                pixels, drop = rd(base + 0x190), rd(base + 0x1b0)
                after = rd(base + 0x1c0)
                row.append({'camera': camera + 1, 'before': before, 'after': after,
                            'pixels': pixels, 'drop': drop, 'stable': before == after})
            stage['rows'].append(row)
            if sample % 20 == 0:
                save()
            time.sleep(0.05)
        stage['after'] = [counters(0x20000000 + camera * 0x200) for camera in range(2)]
        stage['ended'] = time.monotonic()
        save()
        print(json.dumps({'step': step, 'before': stage['before'], 'after': stage['after']}), flush=True)
    doc['status'] = 'completed_restored_140'
    save()
    scope['TX'].close(); scope['RX'].close(); os.close(scope['FD'])
except BaseException as error:
    doc.update(status='uncertain_completion_buffers_held', error=repr(error))
    save()
    print('Fault: no retry or restore; holding FD/buffers', flush=True)
    while True:
        time.sleep(30)
