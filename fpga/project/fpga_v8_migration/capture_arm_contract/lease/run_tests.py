"""Official Pango models + original camera w_* / DMA; candidate-only writes."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
MS = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
VENDOR = Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
CAM = PROJECT / 'source/ov5640/ov5640_ddr'
DMA = PROJECT / 'source/axi_dma'
IP = PROJECT / 'ipcore'
ART = HERE / 'artifacts'
VENDOR_NAMES = ['GTP_GRS', 'GTP_DRM18K_E1', 'GTP_DRM9K_E1',
                'GTP_DRM18K', 'GTP_DRM9K', 'GTP_DRM36K_E1']
ORIGINAL = [CAM / (n + '.v') for n in
            ['ov5640_ddr', 'ov5640_ddr_w', 'ov5640_ddr_w_ctrl', 'ov5640_ddr_w_en']]
ORIGINAL += [DMA / 'axi_dma_write.v', DMA / 'stream_pipe.v', PROJECT / 'source/top.v']
FIFO = [IP / 'ov5640_ddr_fifo_DRM/ov5640_ddr_fifo_DRM.v']
FIFO += sorted((IP / 'ov5640_ddr_fifo_DRM/rtl').glob('ipm*.v'))
FIFO += [IP / 'ov5640_ddr_fifo/ov5640_ddr_fifo.v']
FIFO += sorted((IP / 'ov5640_ddr_fifo/rtl').glob('*.v'))
VENDOR_FILES = [VENDOR / (n + '.v') for n in VENDOR_NAMES]
ORIGINAL += FIFO + VENDOR_FILES + [IP / 'ov5640_ddr_fifo_DRM/rtl/ov5640_ddr_fifo_DRM_Reset_Value.v']


def hashes():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in ORIGINAL}


def scope_hashes():
    paths = set(ORIGINAL)
    for root in [PROJECT / 'source/ov5640', DMA,
                 IP / 'ov5640_ddr_fifo', IP / 'ov5640_ddr_fifo_DRM']:
        paths.update(root.rglob('*.v'))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def command(args, directory, name):
    start = time.time()
    result = subprocess.run([str(x) for x in args], cwd=directory,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.decode('utf-8', errors='replace')
    (directory / (name + '.log')).write_text(output, encoding='utf-8')
    commands.append({'args': [str(x) for x in args], 'cwd': str(directory),
                     'returncode': result.returncode, 'seconds': round(time.time()-start, 3)})
    if result.returncode or '** Error:' in output or '** Fatal:' in output:
        raise RuntimeError(name + ': ' + output[-7000:])
    return output


def scan_modules():
    wanted = {b'fpga_v8_capture_lease', b'fpga_v8_capture_ov5640_ddr'}
    found = {x.decode(): [] for x in wanted}
    for root in [PROJECT / 'source', PROJECT / 'fpga_v8_migration']:
        for p in root.rglob('*.v'):
            if any(x in p.parts for x in ['artifacts', '.venv', '_attic']):
                continue
            for name in re.findall(rb'\bmodule\s+([A-Za-z_][A-Za-z_0-9$]*)', p.read_bytes()):
                if name in wanted:
                    found[name.decode()].append(str(p))
    if any(len(paths) != 1 for paths in found.values()):
        raise RuntimeError('Module name collision: ' + repr(found))
    return found


if __name__ == '__main__':
    from verify_trace import verify
    ART.mkdir(exist_ok=True)
    baseline_path = ART / 'production_hashes_before.json'
    baseline = hashes()
    if baseline_path.exists():
        if json.loads(baseline_path.read_text()) != baseline:
            raise RuntimeError('Production hashes differ from initial capture baseline')
    else:
        baseline_path.write_text(json.dumps(baseline, indent=2) + '\n')
    scope_before = scope_hashes()
    scope_path = ART / 'production_scope_hashes_before.json'
    if scope_path.exists():
        if json.loads(scope_path.read_text()) != scope_before:
            raise RuntimeError('Extended camera/DMA/IP production scope changed')
    else:
        scope_path.write_text(json.dumps(scope_before, indent=2) + '\n')
    commands = []
    names = {"scope":"immutable modules bound into isolated clone"}
    build = ART / 'build'
    build.mkdir(exist_ok=True)
    command([MS / 'vlib.exe', 'work'], build, 'vlib')
    command([MS / 'vlog.exe', '-quiet', '-work', build / 'work', *VENDOR_FILES, *FIFO,
             *ORIGINAL[:6][1:4], DMA / 'axi_dma_write.v', DMA / 'stream_pipe.v',
             HERE.parent.parent / 'capture_lease/fpga_v8_capture_lease.v', HERE.parent.parent / 'capture_lease/fpga_v8_capture_ov5640_ddr.v'],
            build, 'compile_v2001')
    command([MS / 'vlog.exe', '-quiet', '-sv', '-work', build / 'work',
             HERE / 'tb_capture_lease.sv'], build, 'compile_testbench')
    cases = [('small_dual', 2048, 128, 1, 0), ('full_dual', 38400, 640, 1, 0),
             ('small_coop_only', 2048, 128, 0, 0)]
    cases += [('invalid_' + name, 2048 if kind != 4 else 2049, 128, 1, kind)
              for kind, name in enumerate(['overlap', 'bounds', 'alignment', 'odd_length',
                                            'data_width', 'geometry'], 1)]
    results = {}
    for name, words, width, host, bad in cases:
        d = ART / name
        d.mkdir(exist_ok=True)
        output = command([MS / 'vsim.exe', '-c', '-quiet', '-wlf', 'capture.wlf',
                          '-lib', build / 'work', 'tb_capture_lease',
                          '-gWORDS=' + str(words), '-gWIDTH=' + str(width),
                          '-gHOST_REQUIRED=' + str(host), '-gBAD_CFG=' + str(bad),
                          '-do', 'run -all; quit -f'], d, 'simulate')
        if 'CAPTURE_LEASE_PASS' not in output:
            raise RuntimeError(name + ' missing completion: ' + output[-7000:])
        results[name] = verify(d / 'trace.txt', words, width, host, bad)
        results[name]['trace_sha256'] = hashlib.sha256((d / 'trace.txt').read_bytes()).hexdigest()
        print(name, json.dumps(results[name]), flush=True)
    after = hashes()
    (ART / 'production_hashes_after.json').write_text(json.dumps(after, indent=2) + '\n')
    if baseline != after:
        raise RuntimeError('Production source/IP/vendor mutation')
    scope_after = scope_hashes()
    (ART / 'production_scope_hashes_after.json').write_text(json.dumps(scope_after, indent=2) + '\n')
    if scope_before != scope_after:
        raise RuntimeError('Extended camera/DMA/IP production scope changed during tests')
    report = {'official_vendor_models': True, 'verilog_2001_compile': True,
              'module_scan': names, 'production_unchanged': True,
              'production_hash_count': len(after), 'production_scope_hash_count': len(scope_after),
              'candidate_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(HERE.glob('*.v'))},
              'verification_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.sv'))},
              'results': results, 'commands': commands}
    (ART / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('CAPTURE_LEASE_ALL_PASS cases=' + str(len(results)), flush=True)
