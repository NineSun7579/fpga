"""TC04-only ModelSim differential regression against frozen V5; no PDS."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import difflib

HERE = Path(__file__).resolve().parent
V5 = HERE.parent / 'whole_candidate_v5_route_01'
PROJECT = HERE.parents[1]
OUT = HERE / 'receipts' / 'stream_capture'
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
PRIM = Path(os.environ.get('PANGO_SIM_LIB', r'C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(args, label, timeout=600):
    p = subprocess.run([str(x) for x in args], cwd=OUT, capture_output=True, timeout=timeout)
    data = p.stdout + p.stderr
    (OUT / (label + '.log')).write_bytes(data)
    if p.returncode or re.search(rb'\*\* (?:Error|Fatal)', data):
        raise RuntimeError(data.decode(errors='replace')[-12000:])
    return data

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result_file = OUT / 'results.json'
    result_file.unlink(missing_ok=True)
    protected = [PROJECT/'sim/motion/tb_four_motion.sv'] + [p for base in (V5, PROJECT / 'source', PROJECT / 'ipcore',
                  HERE.parent / 'timing_correction_03', HERE.parent / 'timing_correction_02')
                 for p in base.rglob('*') if p.is_file() and p.suffix in ('.v','.sv','.py','.pds','.fdc')]
    before = {str(p): sha(p) for p in protected}
    candidates = [HERE/'rtl/motion_stream_adapter_tc04.v',
                  HERE/'rtl/fpga_v8_capture_ov5640_ddr_tc04.v']
    for cand in candidates:
        module = re.search(rb'\bmodule\s+(\w+)', cand.read_bytes())[1]
        declarations = [str(p) for base in (HERE / 'rtl', PROJECT / 'source', V5 / 'rtl')
                        for p in base.rglob('*.v') if re.search(rb'\bmodule\s+'+module+rb'\b', p.read_bytes())]
        assert declarations == [str(cand)], declarations
    sources = [V5/'rtl/motion_stream_adapter.v', V5/'rtl/block_motion_detector_tc03.v',
               V5/'rtl/fpga_v8_capture_ov5640_ddr.v', *candidates,
               HERE/'tb_motion_tc04.sv', HERE/'tb_capture_tc04.sv']
    sources += [V5/'inputs/source/ov5640/ov5640_ddr'/n for n in
                ('ov5640_ddr_w_en.v','ov5640_ddr_w.v','ov5640_ddr_w_ctrl.v')]
    inc = []
    for n in ('ov5640_ddr_fifo', 'ov5640_ddr_fifo_DRM'):
        ip = V5 / 'inputs/ipcore' / n
        sources += [ip/(n+'.v'), *sorted((ip/'rtl').glob('*.v'))]
        inc.append('+incdir+'+str(ip/'rtl'))
    sources += [PRIM/'GTP_DRM36K_E1.v', PRIM/'GTP_GRS.v']
    inputs = {str(p):sha(p) for p in sources + [Path(__file__).resolve()]}
    if not (OUT/'work').exists(): run([SIM/'vlib.exe','work'],'vlib')
    run([SIM/'vlog.exe','-sv',*inc,*sources],'compile')
    cases = []
    for top, configs in [
        ('tb_motion_tc04', [(640,480,1),(640,480,29),(64,48,202603)]),
        ('tb_capture_tc04', [(38400,1),(38400,29),(2048,202603)])]:
        for cfg in configs:
            params = [f'-gW={cfg[0]}',f'-gH={cfg[1]}',f'-gSEED={cfg[2]}'] if top=='tb_motion_tc04' else [f'-gLEN={cfg[0]}',f'-gSEED={cfg[1]}']
            label = top+'_'+'_'.join(map(str,cfg))
            print('RUN', label, flush=True)
            data = run([SIM/'vsim.exe','-c','-vopt','-voptargs=+acc','work.'+top,*params,
                '-do','onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],label)
            match = re.search(rb'(MOTION|CAPTURE)_TC04_PASS ([^\r\n]+)',data)
            if not match: raise RuntimeError(data.decode(errors='replace')[-12000:])
            metrics = {k.decode():int(v) for k,v in re.findall(rb'(\w+)=(\d+)',match[2])}
            cases.append({'case':label,**metrics})
            print('PASS', metrics, flush=True)
    # Reuse the existing four-channel full-resolution oracle in a new TC04 directory.
    # Its only adapter binding is changed in the generated test artifact.
    four_tb = PROJECT/'sim/motion/tb_four_motion.sv'
    raw = four_tb.read_bytes()
    assert b'motion_stream_adapter adapter' in raw
    bound = OUT/'tb_four_motion_tc04.sv'
    bound.write_bytes(raw.replace(b'motion_stream_adapter adapter',b'motion_stream_adapter_tc04 adapter'))
    register = V5/'inputs/source/motion/motion_register_bank.v'
    run([SIM/'vlog.exe','-sv',register,bound],'four_compile')
    data = run([SIM/'vsim.exe','-c','-vopt','-voptargs=+acc','work.tb_four_motion',
                '-do','onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],'four_motion',900)
    assert b'PASS' in data, data[-6000:]
    assert all(sha(Path(p))==h for p,h in before.items()), 'protected input changed'
    assert all(sha(Path(p))==h for p,h in inputs.items()), 'test input changed'
    paths = json.loads((V5/'evidence/all_reported_failing_paths.json').read_text())
    paths = [p for p in paths if any(s in p['Endpoint'] for s in ('/pixels[','/pixel_count[','/wd_cnt['))]
    (OUT/'v5_full_detail.json').write_text(json.dumps(paths,indent=2))
    (OUT/'path_summary.json').write_text(json.dumps([{
        'startpoint':p['Startpoint'],'endpoint':p['Endpoint'],'slack_ns':p['Slack'],
        'ceco_hops':sum('td' in l and '/CECO' in l for l in p['full_detail'].splitlines())}
        for p in paths],indent=2))
    for name in ('motion_stream_adapter','fpga_v8_capture_ov5640_ddr'):
        src=V5/'rtl'/(name+'.v'); dst=HERE/'rtl'/(name+'_tc04.v')
        (OUT/(name+'.diff')).write_text(''.join(difflib.unified_diff(
            src.read_text().splitlines(True),dst.read_text().splitlines(True),
            fromfile=str(src),tofile=str(dst))))
    (OUT/'protected_sha256.json').write_text(json.dumps(before,indent=2))
    results={'passed':True,'runs':cases,'four_channel_oracle_passed':True,
             'four_tb_sha256':sha(four_tb),'bound_four_tb_sha256':sha(bound),
             'file_sha256':inputs,'protected_files_verified':len(before),
             'pds_invoked':False,'routed_timing_verified':False,
             'capture_fifo_model':'actual frozen V5 IP + PANGO GTP_DRM36K_E1 primitive',
             'capture_public_output_ports_compared':28,
             'baseline':'whole_candidate_v5_route_01/rtl',
             'binding_scope':'motion candidate for four taps; capture wrapper V5 cam5 only; cam6 uses ov5640_ddr'}
    result_file.write_text(json.dumps(results,indent=2))
    print('TC04 ALL PASS', flush=True)

if __name__=='__main__': main()
