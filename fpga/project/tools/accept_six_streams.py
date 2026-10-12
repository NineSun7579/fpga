"""Board-side sustained six-camera DDR freshness and frame capture check."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import mmap
import os
import struct
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=30)
parser.add_argument('--output', default='/tmp/six_acceptance')
parser.add_argument('--diagnostics', action='store_true',
                    help='Sample diagnostic slots using the existing DMA mapping')
args = parser.parse_args()
destination = Path(args.output)
destination.mkdir(parents=True, exist_ok=True)

class Operation(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in ('cur', 'off', 'cmd', 'ddr', 'ln')] + [('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

driver = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
def transact(number, operation):
    result = fcntl.ioctl(driver, 0xC0045300 | number, operation, True)
    if result != 0:
        raise IOError('DMA returned %d' % result)

for command in (0, 1):
    operation = Operation(); operation.cmd = command; operation.ln = 4194304
    transact(2, operation)
receive = mmap.mmap(driver, 4194304, flags=mmap.MAP_SHARED,
                    prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=1048576)

def read(address, size):
    operation = Operation(); operation.ddr = address; operation.ln = size
    transact(5, operation)
    return bytes(receive[:size])

def tag(address):
    return struct.unpack('<I', read(address + 614400, 16)[:4])[0]

def decode_sfp_diagnostics(values, sample, timestamp):
    """Decode physical aligned slot words without opening a device."""
    status, fault5, fault6, pixels5, pixels6, states, rejects = values
    return {
        'sample': sample, 'time': timestamp,
        'raw': [hex(value) for value in values],
        'link': dict(zip(('pll0', 'tx_done', 'rx_done', 'pcs_rx_done', 'sigdet', 'rx_enable'),
                         [bool(status & (1 << bit)) for bit in range(6)])),
        'cameras': [
            {'camera': camera, 'fault': hex(fault),
             'overflow': bool(fault & 0x80000000),
             'short': bool(fault & 0x40000000),
             'dma_abort': bool(fault & 0x20000000),
             'tag_phase': bool(fault & 0x10000000),
             'accepted_pixels': fault & 0x0fffffff,
             'input_pixels': pixels, 'state': (states >> shift) & 0xffff,
             'short_count': (rejects >> shift) & 0xffff}
            for camera, fault, pixels, shift in
            ((5, fault5, pixels5, 0), (6, fault6, pixels6, 16))]}

def sample_sfp_diagnostics(reader, sample):
    values = [struct.unpack('<I', reader(0x20000120 + index * 16, 16)[:4])[0]
              for index in range(7)]
    return decode_sfp_diagnostics(values, sample, time.monotonic())

records = []
started = time.monotonic()
diagnostics = None
try:
    if args.diagnostics:
        diagnostics = (destination / 'diagnostics_during.jsonl').open('w', encoding='ascii')
    while True:
        now = time.monotonic()
        row = {'seconds': now - started, 'tags': []}
        for camera in range(6):
            base = 0x800000 + camera * 0x400000
            row['tags'].append([tag(base), tag(base + 0x200000)])
        records.append(row)
        print(json.dumps(row), flush=True)
        if diagnostics is not None:
            diagnostics.write(json.dumps(sample_sfp_diagnostics(read, len(records) - 1)) + '\n')
            diagnostics.flush()
        if now - started >= args.seconds:
            break
        time.sleep(0.5)
    results = []
    for camera in range(6):
        first = max(records[0]['tags'][camera])
        last = max(records[-1]['tags'][camera])
        unchanged = sum(records[index]['tags'][camera] == records[index - 1]['tags'][camera]
                        for index in range(1, len(records)))
        base = 0x800000 + camera * 0x400000
        capture = None
        for attempt in range(10):
            tags = [tag(base), tag(base + 0x200000)]
            bank = 0 if tags[0] >= tags[1] else 1
            address = base + bank * 0x200000
            before = tag(address)
            content = read(address, 614400)
            after = tag(address)
            if before == after:
                capture = {'bank': bank, 'tag': after,
                           'sha256': hashlib.sha256(content).hexdigest(),
                           'zero_bytes': content.count(0), 'ff_bytes': content.count(255)}
                (destination / ('cam%d.rgb565' % (camera + 1))).write_bytes(content)
                break
        results.append({'camera': camera + 1, 'first': first, 'last': last,
                        'rate': ((last - first) & 0xffffffff) / records[-1]['seconds'],
                        'unchanged_intervals': unchanged, 'capture': capture,
                        'pass': last != first and unchanged == 0 and capture is not None})
    report = {'duration': records[-1]['seconds'], 'results': results,
              'pass': all(result['pass'] for result in results)}
    (destination / 'samples.json').write_text(json.dumps(records, indent=2))
    (destination / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
finally:
    if diagnostics is not None:
        diagnostics.close()
    receive.close()
    os.close(driver)
raise SystemExit(0 if report['pass'] else 2)
