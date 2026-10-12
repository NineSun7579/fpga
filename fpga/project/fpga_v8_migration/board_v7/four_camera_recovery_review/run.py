from pathlib import Path
import hashlib, json, os, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'whole_candidate_v7_route_01'
REC = HERE.parent / 'cdc_boundary_recovery_candidate'
TOOLS = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
VENDOR = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')

def hashes():
    dirs = [ROOT / 'rtl', ROOT / 'inputs', REC,
            HERE.parent / 'cdc_boundary_candidate', HERE.parents[2] / 'source', HERE.parents[2] / 'ipcore']
    result = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in dirs for p in d.rglob('*') if p.is_file()
            and p.suffix.lower() in ('.v', '.vh', '.sv', '.py', '.md', '.pds', '.fdc')}
    for p in [ROOT / 'project.pds', *HERE.parents[2].glob('project*/project.pds')]:
        if p.is_file():
            result[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

before = hashes()
(HERE / 'protected_before.json').write_text(json.dumps(before, indent=2))
# Extract actual startup logic byte-for-byte, not a timing approximation.
top = (ROOT / 'rtl/fpga_v8_cooperative_top_v2_rfg01.v').read_bytes()
binding = (ROOT / 'rtl/ov5640_tc03_binding.v').read_bytes()
start = top[top.index(b'reg [15:0] camera_startup_count'):top.index(b'`ifdef USE_OV5640', top.index(b'reg [15:0] camera_startup_count'))]
power = binding[binding.index(b'reg [$clog2(CLK_FREQ/1000*7)'):binding.index(b'assign cam_pwdn')]
(HERE / 'startup_extract.v').write_bytes(b'module review_startup(input clk_50m,output camera_ctrl_rst_n_out,output cam_rst_n);\nparameter CLK_FREQ=50000000;\n' + start + b'wire rst_n=camera_ctrl_rst_n;\nassign camera_ctrl_rst_n_out=camera_ctrl_rst_n;\n' + power + b'endmodule\n')
sources = [ROOT / 'rtl/axi_dma_write_tc04.v', ROOT / 'inputs/source/axi_dma/stream_pipe.v',
           ROOT / 'rtl/fpga_v8_ddr_write_arbiter.v', ROOT / 'rtl/fpga_v8_ddr_adapter_tc03.v',
           REC / 'cdc_recovery.v', REC / 'cdc_order_meta.v', REC / 'ddr_recovery.v', REC / 'ddr_ctrl_recovery.v',
           ROOT / 'rtl/parent_tc04_e7f19e0d9596.v', ROOT / 'inputs/source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v',
           HERE / 'startup_extract.v']
for name in ('ov5640_cdc_fifo', 'ov5640_ddr_fifo_DRM', 'ov5640_ddr_fifo', 'ddr_fifo16_w', 'ddr_fifo16_r'):
    d = ROOT / 'inputs/ipcore' / name
    sources += [d / (name + '.v'), *sorted((d / 'rtl').glob('*.v'))]
sources += [VENDOR / (n + '.v') for n in ('GTP_DRM18K_E1', 'GTP_DRM36K_E1', 'GTP_GRS')]

def run(build, exe, args, log):
    with (build / log).open('wb') as f:
        result = subprocess.run([str(TOOLS / exe), *map(str, args)], cwd=build, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError((build / log).read_text(errors='replace')[-8000:])

try:
    for name in (sys.argv[1:] or ('startup', 'ledger', 'binding', 'shared')):
        build = HERE / name
        build.mkdir(exist_ok=True)
        if not (build / 'work').exists():
            run(build, 'vlib.exe', ['work'], 'vlib.log')
        run(build, 'vlog.exe', ['-sv', *sources, HERE / ('tb_' + name + '.sv')], 'compile.log')
        run(build, 'vsim.exe', ['-c', '-voptargs=+acc', 'work.tb_' + name, '-do',
                              'onerror {quit -code 1}; run -all; quit -code 0'], 'simulation.log')
        text = (build / 'simulation.log').read_text(errors='replace')
        print('\n'.join(l for l in text.splitlines() if 'REVIEW_' in l or 'FAIL' in l), flush=True)
        assert 'errors=0' in text and 'FAIL' not in text, name
finally:
    after = hashes()
    changed = [p for p in before if before[p] != after.get(p)]
    (HERE / 'protected_result.json').write_text(json.dumps({'files': len(before), 'changed': changed}, indent=2))
    assert not changed, changed
    print('PROTECTED_UNCHANGED', len(before))
