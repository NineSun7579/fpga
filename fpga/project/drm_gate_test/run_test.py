from pathlib import Path
import subprocess
import re
root = Path(__file__).resolve().parent.parent
here = Path(__file__).resolve().parent
binpath = Path('C:/modeltech64_10.6e/win64')
primitive_dir = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
def run(tool, args, logfile):
    result = subprocess.run([str(binpath / (tool+'.exe')), *args], cwd=here, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    (here/logfile).write_bytes(result.stdout)
    print(tool, 'exit', result.returncode, 'log', logfile)
    if result.returncode:
        print(result.stdout.decode(errors='replace')[-8000:])
        raise SystemExit(result.returncode)
    return result.stdout
sources=[]
for name in ('ov5640_ddr_fifo_DRM','ov5640_ddr_fifo'):
    folder=root/'ipcore'/name
    sources += [folder/(name+'.v')]
    sources += [p for p in (folder/'rtl').glob('*.v') if b'module ' in p.read_bytes()]
primitives={}
pending=list(sources)
while pending:
    p=pending.pop()
    for name in re.findall(rb'\bGTP_[A-Za-z0-9_]+',p.read_bytes()):
        text=name.decode('ascii')
        q=primitive_dir/(text+'.v')
        if q.exists() and text not in primitives:
            primitives[text]=q
            pending.append(q)
sources=[primitive_dir/'GTP_GRS.v']+list(primitives.values())+sources
print('Real vendor primitives:', ', '.join(primitives))
original=root/'source/ov5640/ov5640_ddr/ov5640_ddr_w.v'
old=original.with_name(original.name+'.bak_drm_gate')
assert original.read_bytes() == old.read_bytes().replace(b'!(almost_full_drm | empty_drm | almost_full_out)',b'!(empty_drm | almost_full_out)',1)
for variant,target in [('old',old),('fixed',original)]:
    lib=here/('work_'+variant)
    run('vlib',[str(lib)],variant+'_vlib.log')
    run('vlog',['-sv','-work',str(lib),*[str(p) for p in sources],str(target),str(here/'tb_drm_gate.sv')],variant+'_compile.log')
    output=run('vsim',['-c','-lib',str(lib),'tb_drm_gate',*(['+OLD'] if variant=='old' else []),'-do','onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],variant+'_sim.log')
    expected=b'PASS_OLD:' if variant=='old' else b'PASS_FIXED:'
    assert expected in output and b'** Error' not in output and b'** Fatal' not in output, output.decode(errors='replace')[-8000:]
    print('\n'.join(x.decode(errors='replace') for x in output.splitlines() if b'CHECK:' in x or b'PASS_' in x))
print('PASS: old regression reproduction and fixed real-IP simulation')
