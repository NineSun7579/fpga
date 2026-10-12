from pathlib import Path
import hashlib
import os
import re
import subprocess

here = Path(__file__).resolve().parent
project = here.parents[2]
frozen = here.parent.parent / 'whole_candidate_v7_route_01'
capture = frozen / 'inputs/source/ov5640/ov5640/cmos_capture.v'
binding = frozen / 'rtl/ov5640_tc03_binding.v'
names = [b'v7_sfd_candidate', b'v7_sfd_counter', b'tb_v7_sfd_candidate']
conflicts = []
files = 0
# All source searches use bytes, including GBK files. Exclude simulator products.
for base in [project / 'source', here.parent, frozen / 'rtl', frozen / 'inputs/source']:
    for path, dirs, fs in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ('work', 'modelsim', '_info')]
        for f in fs:
            p = Path(path) / f
            if p.suffix.lower() not in ('.v', '.sv') or here in p.parents:
                continue
            files += 1
            data = p.read_bytes()
            for name in names:
                if re.search(rb'\bmodule\s+' + name + rb'\b', data):
                    conflicts.append(str(p))
assert not conflicts, conflicts
print(f'BYTE_MODULE_SCAN files={files} conflicts=0', flush=True)
protected = [capture, binding]
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
bin_dir = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
def run(exe, args, logfile):
    r = subprocess.run([str(bin_dir / exe), *args], cwd=here,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (here / logfile).write_bytes(r.stdout)
    print(r.stdout.decode(errors='replace'), flush=True)
    if r.returncode:
        raise SystemExit(r.returncode)
run('vlib.exe', ['work'], 'vlib.log')
run('vlog.exe', ['-sv', str(capture), 'v7_sfd_candidate.v', 'tb_v7_sfd_candidate.sv'], 'compile.log')
run('vsim.exe', ['-c', '-voptargs=+acc', 'tb_v7_sfd_candidate', '-do',
                 'onerror {quit -code 1}; run -all; quit -code 0'], 'simulation.log')
assert b'SFD_ALL_PASS' in (here / 'simulation.log').read_bytes()
assert b'FAIL ' not in (here / 'simulation.log').read_bytes()
assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
(here / 'source_hashes.txt').write_text(''.join(f'{v}  {k}\n' for k, v in before.items()), encoding='utf8')
print('PROTECTED_INPUT_HASHES_UNCHANGED', flush=True)
