"""Exclusive read probe. Preserve driver FD/buffers on uncertain completion."""
import json
import os
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
source = (root / 'board_peek.py').read_bytes()
source = source.replace(b"os.close(FD)", b"RX.close(); os.close(FD)")
addresses = ['0x40010000', '0x40010010', '0x40010020', '0x400101b0',
             '0x40010400', '0x40010410', '0x40010420', '0x400105b0',
             '0x400105c0', '0x400105d0']
scope = {'__name__': 'probe', '__file__': str(root / 'board_peek.py')}
sys.argv = ['board_peek.py', *addresses]
try:
    exec(compile(source, str(root / 'board_peek.py'), 'exec'), scope)
    (root / 'status.json').write_text(json.dumps({'status': 'completed', 'pid': os.getpid()}))
except BaseException as error:
    (root / 'status.json').write_text(json.dumps({'status': 'uncertain_completion_buffers_held',
        'pid': os.getpid(), 'error': repr(error)}))
    print('Uncertain completion; buffers/FD held. Inspect status.json.', flush=True)
    while True:
        time.sleep(30)
