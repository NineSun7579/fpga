"""Strict candidate latency/parameter checks with the official vendor models."""
import hashlib
import json
import re
import subprocess
from run_sim import HERE, PROJECT, MS, VENDOR, command

CANDIDATE = HERE / 'fpga_v8_conv_mul_pair.v'
DELAYS = (2, 3, 4, 6)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources():
    baseline = json.loads((HERE / 'asset_bounds.json').read_text())['source_sha256']
    observed = {name: sha(PROJECT / name) for name in baseline}
    changed = [name for name in baseline if baseline[name] != observed[name]]
    if changed:
        raise RuntimeError('Production differs from audited source baseline: ' + str(changed))
    return observed


def warnings(directory):
    return [line for tag in ('compile', 'simulate')
            for line in (directory / (tag + '.log')).read_text().splitlines()
            if '** Warning:' in line]


def verify_candidate_structure():
    raw = CANDIDATE.read_bytes()
    raw.decode('ascii')
    declared = re.findall(rb'\bmodule\s+(\w+)', raw)
    if declared != [b'fpga_v8_conv_mul_pair']:
        raise RuntimeError('Unexpected candidate module declarations: ' + str(declared))
    duplicates = [str(p) for p in (PROJECT / 'source').rglob('*.v')
                  if re.search(rb'\bmodule\s+fpga_v8_conv_mul_pair\b', p.read_bytes())]
    if duplicates:
        raise RuntimeError('Production candidate-name collision: ' + str(duplicates))
    vendor_raw = (VENDOR / 'GTP_APM_E2.v').read_bytes()
    ports_raw = vendor_raw.split(b')(', 1)[1].split(b');', 1)[0]
    ports_raw = re.sub(rb'//[^\r\n]*', b'', ports_raw)
    ports = set(re.findall(rb'\b(?:input|output)\s+(?:\[[^]]+\]\s*)?(\w+)', ports_raw))
    inst_raw = raw.split(b'u_apm_two_active_stages (', 1)[1].split(b');', 1)[0]
    connected = re.findall(rb'\.(\w+)\s*\(', inst_raw)
    if set(connected) != ports or len(connected) != len(ports):
        raise RuntimeError('Primitive port coverage is not exact')
    return dict(ascii=True, unique_module=True, primitive_ports_explicit=len(ports),
                candidate_sha256=sha(CANDIDATE),
                vendor_sha256={p.name: sha(p) for p in (VENDOR / 'GTP_APM_E2.v', VENDOR / 'GTP_GRS.v')})


def compile_test(directory):
    directory.mkdir(exist_ok=True)
    command([MS / 'vlib.exe', 'work'], directory, 'vlib')
    command([MS / 'vlog.exe', '-quiet', '-work', 'work',
             VENDOR / 'GTP_GRS.v', VENDOR / 'GTP_APM_E2.v', CANDIDATE,
             HERE / 'tb_candidate_mult.v'], directory, 'compile')


def signed8(value):
    return value - 256 if value >= 128 else value


def check_stream(directory, delay):
    rows = [line.split() for line in (directory / 'mul_observed.txt').read_text().splitlines()]
    if any(len(row) != 7 for row in rows):
        raise RuntimeError('Malformed multiplier stream')
    cycles = [int(row[0]) for row in rows]
    ids = [int(row[1]) for row in rows]
    input_errors, unknown, mismatches = [], [], []
    real_checked = [0, 0]
    lane_mismatches = [0, 0]
    for index, row in enumerate(rows):
        ident = ids[index]
        want_inputs = (ident // 256, (~(ident // 256)) & 255, ident % 256) if ident >= 0 else (0, 0, 0)
        if not -1 <= ident < 65536 or row[2:5] != [f'{v:02x}' for v in want_inputs]:
            input_errors.append(dict(cycle=cycles[index], id=ident, got=row[2:5]))
        # Only the first delay-1 edges are initial fill. All later edges,
        # including idle and flush, are checked. X/Z never drops a sample.
        if index < delay - 1:
            continue
        source_index = index - delay + 1
        source_id = ids[source_index]
        a, b, c = (source_id // 256, (~(source_id // 256)) & 255, source_id % 256) if source_id >= 0 else (0, 0, 0)
        expected = [f'{signed8(a) * c & 65535:04x}', f'{signed8(b) * c & 65535:04x}']
        got = row[5:7]
        if any(char in ''.join(got).lower() for char in 'xz'):
            unknown.append(dict(cycle=cycles[index], source_id=source_id, got=got))
        for lane in range(2):
            if source_id >= 0:
                real_checked[lane] += 1
            if got[lane] != expected[lane]:
                lane_mismatches[lane] += 1
        if got != expected:
            mismatches.append(dict(cycle=cycles[index], source_id=source_id, got=got, expected=expected))
    exact_sampling = (len(rows) == 65560 and cycles == list(range(1, len(rows) + 1))
                      and ids == [-1] * 12 + list(range(65536)) + [-1] * 12)
    result = dict(mul_delay=delay, actual_register_alignment=delay,
                  default_parameter_used=delay == 4, expected_input_pairs=65536,
                  actual_input_pairs=sum(i >= 0 for i in ids), checked_products_per_lane=real_checked,
                  recorded_edges=len(rows), initial_fill_edges=delay - 1,
                  checked_edges_including_idle=len(rows) - delay + 1,
                  exact_sampling=exact_sampling, input_error_count=len(input_errors),
                  unknown_count=len(unknown), mismatch_count=len(mismatches),
                  lane_mismatch_counts=lane_mismatches, first_mismatches=mismatches[:8],
                  first_unknown=unknown[:8], warnings=warnings(directory),
                  pass_exact=exact_sampling and real_checked == [65536, 65536]
                  and not input_errors and not unknown and not mismatches)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def valid_cases():
    results = []
    for delay in DELAYS:
        directory = HERE / f'pair_mult_delay{delay}'
        compile_test(directory)
        text = command([MS / 'vsim.exe', '-c', '-quiet', '-wlf', 'contract.wlf',
                        '-l', 'transcript.log', '-gMUL_DELAY=' + str(delay),
                        'work.fpga_v8_tb_candidate_mult', '-do', 'run -all; quit -f'], directory, 'simulate')
        if 'CANDIDATE_MULT_DONE' not in text:
            raise RuntimeError('Missing complete multiplier marker')
        result = check_stream(directory, delay)
        results.append(result)
        print('candidate multiplier', delay, 'checked', result['checked_products_per_lane'],
              'mismatch', result['mismatch_count'], 'X/Z', result['unknown_count'],
              'PASS', result['pass_exact'], flush=True)
    return results


def invalid_cases():
    results = []
    for int_width, delay in ((8, -1), (8, 0), (8, 1), (7, 4), (9, 4), (16, 4)):
        directory = HERE / f'pair_mult_invalid_int{int_width}_delay{delay}'
        compile_test(directory)
        config_module = ('fpga_v8_config_error_INT_must_be_8' if int_width != 8
                         else 'fpga_v8_config_error_MUL_DELAY_must_be_at_least_2')
        args = [MS / 'vsim.exe', '-modelsimini', (directory / 'modelsim.ini').as_posix(),
                '-c', '-quiet', '-wlf', 'contract.wlf', '-l', 'transcript.log',
                '-gINT=' + str(int_width), '-gMUL_DELAY=' + str(delay),
                'work.fpga_v8_tb_candidate_mult_bad', '-do', 'run -all; quit -f']
        proc = subprocess.run([str(a) for a in args], cwd=directory,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
        text = proc.stdout.decode('utf-8', errors='replace')
        (directory / 'simulate.log').write_text(text)
        rejected = (proc.returncode != 0 and '** Error' in text and config_module in text
                    and 'INVALID_CONFIG_ACCEPTED' not in text)
        result = dict(int_width=int_width, mul_delay=delay, returncode=proc.returncode,
                      expected_missing_config_module=config_module,
                      rejection_phase='elaboration', pass_rejected=rejected)
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        results.append(result)
        print('invalid candidate INT', int_width, 'delay', delay, 'REJECTED', rejected, flush=True)
    return results


def main():
    before = verify_sources()
    structure = verify_candidate_structure()
    valid = valid_cases()
    invalid = invalid_cases()
    after = verify_sources()
    result = dict(structure=structure, valid=valid, invalid=invalid,
                  production_source_sha256=after, production_sources_unchanged=before == after,
                  pass_exact=all(r['pass_exact'] for r in valid)
                  and all(r['pass_rejected'] for r in invalid) and before == after)
    (HERE / 'candidate_mult_results.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['pass_exact']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
