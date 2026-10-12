from pathlib import Path
import subprocess
import hashlib
import json
import sys
import re

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
BIN = Path(r'C:/modeltech64_10.6e/win64')
SOURCES = [PROJECT / 'source/sfp/video_async_fifo.v',
           PROJECT / 'source/sfp/sfp_rx_cam_if.v'] + [
    PROJECT / ('source/ov5640/ov5640_ddr/' + n + '.v') for n in
    ['ov5640_ddr', 'ov5640_ddr_w', 'ov5640_ddr_w_ctrl', 'ov5640_ddr_w_en']]
STUB = PROJECT / 'sim/dma_timeout_repro/fifo_models.sv'

def hashes():
    return {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SOURCES + [STUB]}

def run(args, logfile):
    proc = subprocess.run([str(BIN / args[0])] + args[1:], cwd=HERE,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE / logfile).write_bytes(proc.stdout)
    if proc.returncode:
        raise RuntimeError(f'{logfile}: exit {proc.returncode}')
    return proc.stdout

before = hashes()
(HERE / 'source_hashes_before.json').write_text(json.dumps(before, indent=2))
if not (HERE / 'work').exists():
    run(['vlib.exe', 'work'], 'vlib.log')
run(['vlog.exe', '-work', 'work', '-sv'] + [str(p) for p in SOURCES] +
    [str(STUB), str(HERE / 'tb_receiver.sv')], 'compile.log')

cases = [('baseline_full', 480, 8, 256, 6, 3),
         ('delayed_100us_full', 480, 12500, 256, 6, 6),
         ('short_fast_dma', 2, 64, 0, 6, 6),
         ('short_256', 2, 8, 256, 6, 3),
         ('short_1024', 2, 8, 1024, 3, 3),
         ('short_1100', 2, 8, 1100, 3, 3),
         ('delayed_tail_19000', 2, 12500, 19000, 6, 6),
         ('delayed_tail_21000', 2, 12500, 21000, 3, 3)]
summary = []
for name, h, blank, tail, e5, e6 in cases:
    script = ('onerror {quit -code 1 -force}\n'
              f'vsim -onfinish stop -voptargs=+acc -gH={h} -gBLANK={blank} -gTAIL={tail} '
              f'work.tb_receiver +EXP5={e5} +EXP6={e6}\n'
              'run -all\nquit -code 0 -force\n')
    (HERE / (name + '.do')).write_text(script)
    print('Running', name, flush=True)
    previous = HERE / (name + '.log')
    reuse = '--resume' in sys.argv and previous.exists()
    out = previous.read_bytes() if reuse else b''
    counts = re.findall(rb'published=(\d+)', out)
    config_matches = all(t.encode() in out for t in
                         [f'H={h} FRAMES=6 BLANK_RX={blank}', f'TAIL_AXI={tail} '])
    if not (b'PASS receiver end-frame experiment' in out and b'Fatal:' not in out
            and counts == [str(e5).encode(), str(e6).encode()] and config_matches):
        out = run(['vsim.exe', '-c', '-do', name + '.do'], name + '.log')
    if b'PASS receiver end-frame experiment' not in out or b'Fatal:' in out:
        raise RuntimeError(f'{name}: no PASS (inspect log)')
    lines = [l.decode('ascii', errors='replace') for l in out.splitlines()
             if b'CONFIG ' in l or b'RESULT ' in l or b'PASS receiver' in l]
    summary += [name] + lines
    print('\n'.join(lines), flush=True)
(HERE / 'results.log').write_text('\n'.join(summary) + '\n')
after = hashes()
(HERE / 'source_hashes_after.json').write_text(json.dumps(after, indent=2))
if before != after:
    raise RuntimeError('Production source changed concurrently during simulation')
print('PASS all cases; production modules and reused FIFO stub hashes unchanged')
