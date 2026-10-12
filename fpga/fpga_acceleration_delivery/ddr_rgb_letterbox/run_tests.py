"""Run isolated DDR endpoint RTL with an independent RGB byte oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT.parents[1]


def oracle(width, height, out_height, top, frame):
    data = bytearray([114]) * (width * out_height * 3)
    for i in range(width * height):
        p = (i ^ (frame * 0x1357)) & 65535
        r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
        offset = (top * width + i) * 3
        data[offset:offset + 3] = bytes(((r << 3) | (r >> 2),
                                       (g << 2) | (g >> 4),
                                       (b << 3) | (b >> 2)))
    return data


def production_hashes():
    paths = [p for folder in ('source', 'ipcore') for p in (BASELINE / folder).rglob('*')
             if p.is_file()]
    paths.append(BASELINE / 'project/project.pds')
    return {p.relative_to(BASELINE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modelsim-bin', default='C:/modeltech64_10.6e/win64')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    tools = Path(args.modelsim_bin)
    out = ROOT / 'artifacts'
    out.mkdir(exist_ok=True)
    before = production_hashes()
    (out / 'production_before.json').write_text(json.dumps(before, indent=2))
    library = out / 'work'

    def run(argv, cwd, log):
        p = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                           text=True, errors='replace', timeout=240)
        text = p.stdout + p.stderr
        log.write_text(text)
        if p.returncode or '** Error' in text or 'FAIL ' in text or '** Fatal' in text:
            raise RuntimeError(f'{log}:\n{text[-4000:]}')
        return text

    if not library.exists():
        run([tools / 'vlib.exe', library], out, out / 'vlib.log')
    rtl = sorted((ROOT / 'rtl').glob('*.v'))
    # Byte-level module scan, including GBK production RTL.
    modules = {}
    for p in (BASELINE / 'source').rglob('*.v'):
        for name in re.findall(rb'\bmodule\s+(\w+)', p.read_bytes()):
            modules.setdefault(name, []).append(str(p))
    for p in rtl:
        raw = p.read_bytes()
        raw.decode('ascii')
        for name in re.findall(rb'\bmodule\s+(\w+)', raw):
            assert name not in modules, (name, modules.get(name))
            modules[name] = [str(p)]
    log = run([tools / 'vlog.exe', '-work', library, '-vlog01compat', *rtl],
              out, out / 'compile.log')
    assert 'Errors: 0' in log
    log = run([tools / 'vlog.exe', '-work', library, '-sv',
               ROOT / 'sim/tb_delivery_rgb_ddr.sv'], out, out / 'compile_tb.log')
    assert 'Errors: 0' in log
    cases = [('burst_boundary_stalls', 45, 5, 7, 1, 1, 0),
             ('burst_read_fault', 45, 5, 7, 1, 1, 1),
             ('burst_write_fault', 45, 5, 7, 1, 1, 2),
             ('burst_last_fault', 45, 5, 7, 1, 1, 3),
             ('odd_stalls', 4, 3, 5, 1, 1, 0),
             ('no_pad', 2, 2, 2, 0, 0, 0),
             ('final_overflow', 1, 1, 6, 2, 1, 0),
             ('read_fault', 4, 3, 5, 1, 1, 1),
             ('write_fault', 4, 3, 5, 1, 1, 2),
             ('read_last_fault', 4, 3, 5, 1, 1, 3)]
    if not args.quick:
        cases += [('full_ready', 640, 480, 640, 80, 0, 0),
                  ('full_stalls', 640, 480, 640, 80, 1, 0)]
    results = []
    for name, w, h, oh, top, stall, fault in cases:
        folder = out / name
        folder.mkdir(exist_ok=True)
        frames = [oracle(w, h, oh, top, f) for f in range(2)]
        (folder / 'expected.hex').write_text(''.join(f'{b:02x}\n' for f in frames for b in f))
        log = run([tools / 'vsim.exe', '-c', '-quiet', '-onfinish', 'exit',
                   '-lib', library, 'tb_delivery_rgb_ddr', f'-gW={w}', f'-gH={h}',
                   f'-gOH={oh}', f'-gTOP={top}', f'-gSTALL={stall}', f'-gFAULT={fault}',
                   '-do', 'onerror {quit -code 2}; run -all; quit -code 0'],
                  folder, folder / 'simulation.log')
        assert 'PASS tb_delivery_rgb_ddr' in log
        actual = [bytearray(), bytearray()]
        for line in (folder / 'writes.txt').read_text().splitlines():
            f, addr, word, mask = line.split()
            f, mask = int(f), int(mask, 16)
            if fault and f == 0:
                continue
            assert int(addr, 16) == 0x200000 + (len(actual[f]) // 256) * 256
            assert mask and not (mask & (mask + 1))
            actual[f].extend(int(word, 16).to_bytes(16, 'little')[:mask.bit_count()])
        for f in range(2):
            if not fault or f:
                assert actual[f] == frames[f], (name, f)
        results.append({'case': name, 'cycles': int(re.search(r'cycles=(\d+)', log)[1]),
                        'bytes_verified': sum(len(x) for x in actual),
                        'frame_sha256': [hashlib.sha256(x).hexdigest() for x in actual if x]})
    after = production_hashes()
    (out / 'production_after.json').write_text(json.dumps(after, indent=2))
    assert before == after, 'Production files changed during validation'
    report = {'scope': 'RTL simulation only; no PDS, board, or FPS evidence',
              'production_files_unchanged': len(before), 'module_collision_scan': 'pass',
              'results': results}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
