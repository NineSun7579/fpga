import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project/tools'))
from board_host import ssh_connect

REMOTE = r'''
import ctypes, hashlib, json, os, pathlib, subprocess, sys, time
seconds = float(sys.argv[1])
def read(path):
    try: return pathlib.Path(path).read_text().strip()
    except OSError: return None
def process(pid):
    value = read('/proc/%d/stat' % pid)
    if not value: return None
    fields = value[value.rfind(')')+2:].split()
    return {'pid': pid, 'state': fields[0], 'ticks': int(fields[11])+int(fields[12]),
            'starttime': fields[19]}
viewers = []
for path in pathlib.Path('/proc').iterdir():
    if not path.name.isdigit(): continue
    try:
        exe = os.readlink(path/'exe')
        if 'detview' not in exe: continue
        item = process(int(path.name))
        item.update(exe=exe, argv=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),
                    sha256=hashlib.sha256((path/'exe').read_bytes()).hexdigest())
        viewers.append(item)
    except OSError: pass
libc = ctypes.CDLL(None, use_errno=True)
class Timespec(ctypes.Structure):
    _fields_ = [('sec',ctypes.c_long),('nsec',ctypes.c_long)]
def syscall_monotonic():
    if os.uname().machine != 'aarch64': return None
    result = Timespec()
    rc = libc.syscall(ctypes.c_long(113), ctypes.c_int(1), ctypes.byref(result))
    return result.sec*1000000000+result.nsec if rc == 0 else None
def clocks():
    return {'monotonic_ns':time.clock_gettime_ns(time.CLOCK_MONOTONIC),
            'raw_ns':time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW),
            'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),
            'realtime_ns':time.time_ns(), 'syscall_monotonic_ns':syscall_monotonic()}
def emit(value): print(json.dumps(value), flush=True)
frequency_paths = list(pathlib.Path('/sys/class/devfreq').glob('*/cur_freq'))
frequency_paths += list(pathlib.Path('/sys/devices/system/cpu/cpufreq').glob('policy*/scaling_cur_freq'))
def frequencies(): return {str(path):read(path) for path in frequency_paths}
emit({'kind':'identity', 'viewers':viewers, 'clocksource':read('/sys/devices/system/clocksource/clocksource0/current_clocksource'),
      'available_clocksources':read('/sys/devices/system/clocksource/clocksource0/available_clocksource'),
      'hz':os.sysconf('SC_CLK_TCK'), 'schedstats':read('/proc/sys/kernel/sched_schedstats'), 'clocks':clocks(),
      'frequencies':frequencies()})
started = time.monotonic()
count = 0
while time.monotonic()-started < seconds:
    sample = {'kind':'sample','index':count,'clocks':clocks(), 'load':read('/proc/loadavg'),
              'cpu':read('/proc/stat').splitlines()[0], 'viewers':[], 'frequencies':frequencies()}
    for expected in viewers:
        item = process(expected['pid'])
        if item is None or item['starttime'] != expected['starttime']:
            emit({'kind':'identity_changed','pid':expected['pid'],'index':count})
            sys.exit(2)
        threads = []
        for task in pathlib.Path('/proc/%d/task'%item['pid']).iterdir():
            stat = read(task/'stat')
            if not stat: continue
            fields = stat[stat.rfind(')')+2:].split()
            threads.append({'tid':int(task.name), 'state':fields[0], 'cpu_ticks':int(fields[11])+int(fields[12]),
                            'schedstat':read(task/'schedstat'), 'wchan':read(task/'wchan')})
        item['threads'] = threads
        sample['viewers'].append(item)
    emit(sample)
    count += 1
    time.sleep(1)
final = []
for expected in viewers:
    item = process(expected['pid'])
    if item:
        item['sha256'] = hashlib.sha256(pathlib.Path('/proc/%d/exe'%item['pid']).read_bytes()).hexdigest()
    final.append(item)
emit({'kind':'finished', 'samples':count,'clocks':clocks(),'viewers':final,
      'dmesg_tail':subprocess.run(['dmesg'],capture_output=True,text=True,timeout=5).stdout.splitlines()[-100:]})
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error('seconds must be between 1 and 600')
    log = ROOT / 'log/100h_motion' / ('clock_stall_' + time.strftime('%Y%m%d_%H%M%S') + '.jsonl')
    log.parent.mkdir(parents=True, exist_ok=True)
    client = ssh_connect()
    records = []
    print('Read-only clock/thread capture: ' + str(log), flush=True)
    try:
        command = 'sudo -n python3 -u -c ' + shlex.quote(REMOTE) + ' ' + str(args.seconds)
        _, stdout, stderr = client.exec_command(command, timeout=args.seconds + 45)
        with log.open('x', encoding='utf-8') as output:
            for line in stdout:
                record = json.loads(line)
                record['local_received_monotonic_ns'] = time.monotonic_ns()
                record['local_received_realtime_ns'] = time.time_ns()
                output.write(json.dumps(record) + '\n')
                output.flush()
                records.append(record)
                if record['kind'] != 'sample' or record['index'] % 10 == 0:
                    print(time.strftime('%H:%M:%S'), record['kind'], record.get('index',''), flush=True)
        code = stdout.channel.recv_exit_status()
        errors = stderr.read().decode(errors='replace')
        samples = [record for record in records if record['kind'] == 'sample']
        gaps = []
        for before, after in zip(samples, samples[1:]):
            gaps.append({name:(after['clocks'][name]-before['clocks'][name])/1e6
                         for name in ('monotonic_ns','raw_ns','boottime_ns','realtime_ns')})
            gaps[-1]['local_receive_ms'] = (after['local_received_monotonic_ns']-before['local_received_monotonic_ns'])/1e6
        skew = [abs(record['clocks']['monotonic_ns']-record['clocks']['syscall_monotonic_ns'])/1e6
                for record in samples if record['clocks']['syscall_monotonic_ns'] is not None]
        result = {'exit_code':code, 'stderr':errors,'raw':str(log),'samples':len(samples),
                  'identity':records[0] if records else None,
                  'finished':next((record for record in records if record['kind']=='finished'),None),
                  'max_gaps_ms':{name:max((gap[name] for gap in gaps),default=None)
                                 for name in ('monotonic_ns','raw_ns','boottime_ns','realtime_ns','local_receive_ms')},
                  'max_vdso_syscall_skew_ms':max(skew,default=None),
                  'gaps_over_1500_ms':[gap for gap in gaps if gap['monotonic_ns']>1500],
                  'raw_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
        log.with_suffix('.summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({key:result[key] for key in ('exit_code','samples','max_gaps_ms','max_vdso_syscall_skew_ms')},indent=2),flush=True)
        if code:
            raise RuntimeError('Read-only capture did not finish: ' + errors)
    finally:
        client.close()


if __name__ == '__main__':
    main()
