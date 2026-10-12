"""Local ModelSim test; production and frozen RTL are read-only inputs."""
from pathlib import Path
import hashlib
import os
import subprocess

here = Path(__file__).resolve().parent
frozen = here.parents[1] / 'whole_candidate_v7_route_01'
rtl = frozen / 'inputs/source/ov5640/ov5640_ddr'
sources = [frozen / 'rtl/ov5640_ddr_tc04.v'] + [rtl / n for n in
    ('ov5640_ddr_w_en.v', 'ov5640_ddr_w.v', 'ov5640_ddr_w_ctrl.v')]
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
build = here / 'ddr_modelsim'
build.mkdir(exist_ok=True)
tools = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
def run(args):
    print('COMMAND:', subprocess.list2cmdline([str(x) for x in args]), flush=True)
    subprocess.run([str(x) for x in args], cwd=build, check=True)
if not (build / 'work').exists():
    run([tools / 'vlib.exe', 'work'])
run([tools / 'vlog.exe', '-sv', '-work', 'work', *sources,
     here / 'ddr_fifo_models.sv', here / 'tb_ddr_boundary.sv'])
run([tools / 'vsim.exe', '-c', '-voptargs=+acc', '-l', 'ddr_boundary.log',
     'work.tb_ddr_boundary', '-do', 'onerror {quit -code 1}; run -all; quit -code 0'])
log = (build / 'ddr_boundary.log').read_bytes()
assert b'DDR_BOUNDARY_DONE checks=61 errors=0' in log, 'Missing clean assertion result'
assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(here / 'ddr_frozen_sha256.txt').write_text('\n'.join(f'{h}  {p}' for p,h in before.items())+'\n')
print('Frozen input hashes unchanged.')
