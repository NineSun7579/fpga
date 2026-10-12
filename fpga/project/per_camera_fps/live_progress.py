"""Read-only local progress console; does not start builds or touch hardware."""
import json
import argparse
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / 'project/per_camera_fps'
SHELL = Path.home() / '.local/share/opencode/shell/292d05f2ca9892d4af74cecc9a48e5b592e79454'
positions = {}
states = {}
parser = argparse.ArgumentParser()
parser.add_argument('--run', help='Show one FPGA build directory')
parser.add_argument('--host-diagnosis', action='store_true', help='Show host stall diagnosis progress')
parser.add_argument('--hardware-acceleration', action='store_true', help='Show hardware acceleration probe progress')
args = parser.parse_args()

def emit(label, text):
    print(time.strftime('%H:%M:%S') + ' [' + label + '] ' + text, flush=True)

def tail(path, label):
    try:
        with path.open('rb') as stream:
            size = path.stat().st_size
            offset = positions.get(path, max(0, size - 1800))
            if offset > size:
                offset = 0
            stream.seek(offset)
            data = stream.read(32768)
            positions[path] = stream.tell()
        if data:
            text = data.decode('utf-8', errors='replace')
            if '\ufffd' in text:
                text = data.decode('gb18030', errors='replace')
            for line in text.splitlines():
                if line.strip():
                    emit(label, line[:1000])
    except (OSError, ValueError):
        pass

print(('FPGA / RK3568 hardware acceleration' if args.hardware_acceleration else '40/30 FPS optimization') + ' - LIVE PROGRESS', flush=True)
print('Target: CAM1/2/5/6 fresh 40 fps; CAM3/4 fresh 30 fps.', flush=True)
print('Read-only monitor. Ctrl+C closes this monitor; builds continue.', flush=True)
print('Progress comes from actual logs; no estimated percentages.', flush=True)
heartbeat = 0
monitor_started = time.time()
try:
    while True:
        runs = list((TASK / 'fpga').glob('recovery_*')) + list((TASK / 'pll56').glob('build_*'))
        if args.run:
            runs = [Path(args.run).resolve()]
        if args.host_diagnosis or args.hardware_acceleration:
            runs = []
        for run in sorted(runs):
            receipt = run / 'receipt.json'
            try:
                r = json.loads(receipt.read_text(encoding='utf-8'))
                state = (r.get('status'), r.get('stage'), r.get('error'))
                if states.get(receipt) != state:
                    states[receipt] = state
                    emit('FPGA ' + run.name, str(state) + ' started=' + str(r.get('started')) + ' finished=' + str(r.get('finished')))
                    if r.get('bit_sha256'):
                        emit('BIT SHA256', r['bit_sha256'])
            except (OSError, ValueError):
                pass
            for log in sorted(run.glob('*.log')):
                if log.name != 'vendor_help.log':
                    tail(log, 'FPGA ' + log.stem)
        deployment_receipts = [] if args.host_diagnosis or args.hardware_acceleration else list((TASK / 'fpga').glob('**/receipt.json')) + list((TASK / 'pll56').glob('**/receipt.json'))
        deployment_receipts += list((TASK / 'host_stall').glob('**/*receipt.json'))
        deployment_receipts += list((ROOT / 'project/hardware_acceleration').glob('**/*receipt.json'))
        for receipt in sorted(deployment_receipts):
            if receipt.stat().st_mtime < time.time() - 7200:
                continue
            try:
                r = json.loads(receipt.read_text(encoding='utf-8'))
                state = (r.get('status'), r.get('stage'), r.get('state'), r.get('error'), r.get('blocker'))
                if states.get(receipt) != state:
                    states[receipt] = state
                    emit('STATUS', str(receipt.relative_to(ROOT)) + ' ' + str(state))
            except (OSError, ValueError):
                pass
        if not (args.host_diagnosis or args.hardware_acceleration):
            tail(SHELL / 'sh_1057c6cfb001zd2h7PCUmmDdb1.out', 'HOST direct-display build')
        for log in sorted(SHELL.glob('*.out')):
            if log.stat().st_mtime >= monitor_started - 300:
                tail(log, 'TASK ' + log.stem)
        for receipt in sorted((ROOT / 'log/100h_motion').glob('motion_viewer_*.json')):
            if receipt.stat().st_mtime < time.time() - 3600:
                continue
            try:
                r = json.loads(receipt.read_text(encoding='utf-8'))
                events = r.get('events', [])
                state = (len(events), events[-1].get('state') if events else None)
                if states.get(receipt) != state:
                    states[receipt] = state
                    emit('BOARD', receipt.name + ' ' + str(state))
            except (OSError, ValueError):
                pass
        for summary in sorted((ROOT / 'log/100h_motion').glob('clock_stall_*.summary.json')):
            try:
                if summary.stat().st_mtime < monitor_started - 1800:
                    continue
                signature = summary.stat().st_mtime_ns
                if states.get(summary) != signature:
                    states[summary] = signature
                    report = json.loads(summary.read_text(encoding='utf-8'))
                    emit('CLOCK CHECK', summary.name + ' samples=' + str(report.get('samples')) +
                         ' max_intervals_ms=' + str(report.get('max_gaps_ms')))
            except (OSError, ValueError):
                pass
        if time.monotonic() - heartbeat >= 10:
            emit('LIVE', 'Monitoring RGA / RKNN probes and diagnostic receipts...' if args.hardware_acceleration else 'Monitoring host stall diagnosis and build receipts...' if args.host_diagnosis else 'Monitoring FPGA repair, host build and board test receipts...')
            heartbeat = time.monotonic()
        time.sleep(1)
except KeyboardInterrupt:
    print('Monitor closed. Build/test processes remain running.', flush=True)
