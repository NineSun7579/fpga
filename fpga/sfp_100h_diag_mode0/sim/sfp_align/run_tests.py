"""Byte/K-accurate 2SKIP mutations before packing into the HSST stub's RX bus."""
from pathlib import Path
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
BIN = Path('C:/modeltech64_10.6e/win64')


def ctrl(st=0):
    return [(0xBC, 1), (0x28, 0), (st, 0), (0xBC, 1)]


def stimulus(kind, pixels):
    words = [ctrl() for _ in range(24)]
    marker = len(words) - 1
    high_count = 8 if kind == 'delete_sof_repeated' else 1
    words += [ctrl(0x20) for _ in range(high_count)] + [ctrl() for _ in range(8)]
    payload_marker = len(words)
    golden = [(0x1000 + i) & 0xFFFF for i in range(pixels)]
    for i in range(0, pixels, 2):
        words += [ctrl(), ctrl(), [(golden[i] & 255, 0), (golden[i] >> 8, 0),
                                  (golden[i+1] & 255, 0), (golden[i+1] >> 8, 0)]]
    words += [ctrl() for _ in range(128)]
    # Select an actual BC(K)/28(D) pair embedded in a video control.
    edit_word = marker
    if kind in ('delete_sof', 'delete_sof_repeated'):
        edit_word = marker + 1
    elif kind in ('delete_payload', 'insert_payload', 'delete_before_data', 'insert_before_data'):
        edit_word = payload_marker + 12  # before the fifth two-pixel data word
        if kind.endswith('before_data'):
            edit_word += 1  # last control immediately before data
    symbols = [symbol for word in words for symbol in word]
    pos = edit_word * 4
    if kind.startswith('delete'):
        assert symbols[pos:pos+2] == [(0xBC, 1), (0x28, 0)]
        del symbols[pos:pos+2]
    elif kind.startswith('insert'):
        assert symbols[pos:pos+2] == [(0xBC, 1), (0x28, 0)]
        symbols[pos:pos] = [(0xBC, 1), (0x28, 0)]
    return symbols, golden


def run(cmd, log):
    result = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = result.stdout.decode(errors='replace')
    log.write_text(text)
    if result.returncode:
        raise RuntimeError(f'{cmd[0]} failed: see {log}')
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='also measure a 1280x480 frame')
    parser.add_argument('--probe', action='store_true', help='isolated same-cycle hit-selection experiment')
    args = parser.parse_args()
    out = ROOT / ('results_probe' if args.probe else 'results')
    out.mkdir(exist_ok=True)
    if args.probe:
        original = (ROOT/'../../source/sfp/sfp_rx_link.v').read_bytes()
        old = b'case (rot)'
        new = b"case (hit0 ? 2'd0 : hit1 ? 2'd1 : hit2 ? 2'd2 : hit3 ? 2'd3 : rot)"
        assert original.count(old) == 1
        # Generated fixture only; production bytes are never written.
        (out/'sfp_rx_link_probe.v').write_bytes(original.replace(old, new))
        script = ('onerror {quit -code 1 -force}; vlib work_probe; '
                  'vlog -work work_probe -sv hsst_sfp_stub.v '
                  f'{out.name}/sfp_rx_link_probe.v ../../source/sfp/sfp_video_rx.v tb_sfp_align.v; '
                  'quit -code 0 -force')
        run([str(BIN/'vsim.exe'), '-c', '-do', script], out/'compile.log')
    else:
        run([str(BIN/'vsim.exe'), '-c', '-do', 'run.do'], out/'compile.log')
    cases = [(kind, offset, 64) for kind in
             ['baseline', 'delete_before_sof', 'insert_before_sof', 'delete_sof',
              'delete_sof_repeated', 'delete_payload', 'insert_payload',
              'delete_before_data', 'insert_before_data']
             for offset in range(4)]
    if args.full:
        cases += [('baseline', 0, 1280*480), ('delete_before_sof', 0, 1280*480),
                  ('delete_payload', 0, 1280*480), ('delete_before_data', 0, 1280*480),
                  ('insert_before_data', 0, 1280*480)]
    results = []
    for kind, offset, pixels in cases:
        name = f'{kind}_off{offset}_n{pixels}'
        symbols, golden = stimulus(kind, pixels)
        # Offset means the first unmodified control starts at this byte lane.
        symbols = [(0xC5, 0)] * offset + symbols
        symbols += [(0xC5, 0)] * ((-len(symbols)) % 4)
        vector = out/f'{name}.vec'
        with vector.open('w') as f:
            for i in range(0, len(symbols), 4):
                chunk = symbols[i:i+4]
                d = sum(b << (8*j) for j, (b, k) in enumerate(chunk))
                k = sum(k << j for j, (b, k) in enumerate(chunk))
                f.write(f'{d:08x} {k:x}\n')
        lib = 'work_probe' if args.probe else 'work'
        text = run([str(BIN/'vsim.exe'), '-c', '-voptargs=+acc', f'{lib}.tb_sfp_align',
                    f'+VECTOR={out.name}/{name}.vec', f'+PIXELS={out.name}/{name}.pixels',
                    f'+TRACE={out.name}/{name}.trace', '-do', 'run -all; quit -code 0 -force'],
                   out/f'{name}.log')
        match = re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)', text)
        if not match:
            raise RuntimeError(f'no RESULT for {name}')
        row = dict(zip(['pixels', 'frame_pixels', 'sof', 'controls', 'relocks', 'overflow'],
                       map(int, match.groups())))
        observed = [int(l, 16) for l in (out/f'{name}.pixels').read_text().splitlines()]
        row.update(case=name, expected=pixels, exact_pixels=(observed == golden),
                   first_mismatch=next((i for i, (a,b) in enumerate(zip(observed,golden)) if a != b), None))
        if pixels == 64:
            row['observed'] = [f'{p:04x}' for p in observed]
        results.append(row)
        print(json.dumps({k:v for k,v in row.items() if k != 'observed'}), flush=True)
        assert row['overflow'] == 0, name
        if kind == 'baseline':
            assert row['exact_pixels'] and row['sof'] == 1 and row['frame_pixels'] == pixels, row
    (out/'summary.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
