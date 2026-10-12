"""Focused ModelSim test for the independent six-camera ownership candidate."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
BIN=Path('C:/modeltech64_10.6e/win64')
ART=ROOT/'six_camera_verification'
ART.mkdir(exist_ok=True)
work=ART/'work'
subprocess.run([str(BIN/'vlib.exe'),str(work)],check=True,cwd=ROOT)
sources=[ROOT/'integrated_six/source/delivery/delivery_regs.v',
         ROOT/'integrated_six/source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v',
         ROOT/'six_camera_tb.sv']
with (ART/'compile.log').open('w') as log:
    subprocess.run([str(BIN/'vlog.exe'),'-work',str(work),'-sv',*map(str,sources)],check=True,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
with (ART/'simulation.log').open('w') as log:
    subprocess.run([str(BIN/'vsim.exe'),'-c','-quiet','-onfinish','exit','-lib',str(work),
                    'tb_six_camera_ownership','-do','onerror {quit -code 2}; run -all; quit -code 0'],
                   check=True,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
text=(ART/'simulation.log').read_text(errors='replace')
assert 'PASS six-camera ownership' in text
print('PASS six-camera ownership verification')
