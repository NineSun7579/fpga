from pathlib import Path
import subprocess, hashlib, re, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RTL = ROOT / 'source/axi_crossbar/ddr_w_arb.v'
BIN = Path(r'C:\modeltech64_10.6e\win64')
before = RTL.read_bytes()
# All port discovery/search is performed on bytes; no production file writes.
ports = re.findall(rb'(input|output)\s+wire\s*(\[[^\]]+\])?\s*(\w+)\s*[,\n]', before)
decl, connections = [], []
for direction, width, name in ports:
    n = name.decode('ascii'); w = width.decode('ascii')
    if re.match(rb'm[012]_', name):
        idx = int(n[1]); suffix = n[3:]
        if idx == 0:
            decl.append(f'{"reg" if direction == b"input" else "wire"} {w} {suffix} [0:2];')
        connections.append(f'.{n}({suffix}[{idx}])')
    else:
        if n not in ('clk', 'rst'):
            decl.append(f'{"reg" if direction == b"input" else "wire"} {w} {n};')
        connections.append(f'.{n}({n})')
template = (HERE / 'bench.template.sv').read_bytes()
bench = template.replace(b'@@DECL@@', '\n'.join(decl).encode()).replace(b'@@CONNECT@@', ',\n'.join(connections).encode())
(HERE / 'tb.sv').write_bytes(bench)

def run(args, log):
    p = subprocess.run([str(BIN / args[0])] + args[1:], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE / log).write_bytes(p.stdout)
    print(p.stdout.decode(errors='replace'))
    if p.returncode:
        raise RuntimeError(f'{args[0]} exited {p.returncode}')

if not (HERE / 'work').exists():
    run(['vlib.exe', 'work'], 'vlib.log')
run(['vlog.exe', '-sv', '-work', 'work', str(RTL), 'tb.sv'], 'compile.log')
results = []
for mode in (0, 1, 2):
    log = f'mode{mode}.log'
    run(['vsim.exe', '-c', '-l', f'transcript{mode}.log', 'work.tb', f'+MODE={mode}', '-do', 'run -all; quit -f'], log)
    data = (HERE / log).read_bytes()
    passed = (b'PASS THROUGHPUT' in data) if mode < 2 else (b'AW_STABILITY_PASS' in data)
    label = ('PASS THROUGHPUT' if mode < 2 else 'PASS AW PAYLOAD STABILITY (fixed)')
    results.append(f'mode={mode}: ' + (label if passed else 'UNEXPECTED RESULT'))
assert RTL.read_bytes() == before, 'Production RTL changed'
summary = '\n'.join(results) + '\nRTL SHA256 unchanged: ' + hashlib.sha256(before).hexdigest() + '\n'
(HERE / 'summary.txt').write_bytes(summary.encode())
print(summary)
if any('UNEXPECTED' in x for x in results):
    sys.exit(1)
