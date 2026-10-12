"""Complete MAC streams through unique test cores and the persistent candidate."""
import json
import re
from run_sim import HERE, RTL, MS, VENDOR, command, make_case
from run_candidate_mult import CANDIDATE, sha, verify_sources, verify_candidate_structure, warnings

CASES = [('mac3_ci3_co3', 3, 3, 3, 0, None),
         ('mac1_ci3_co3', 1, 3, 3, 0, None),
         ('mac11_ci3_co3', 1, 3, 3, 1, None),
         ('mac3_ci19_co3', 3, 19, 3, 0, None),
         ('mac_model_task000', 3, 3, 16, 0, 0)]


def copy_cores():
    directory = HERE / 'pair_core_rtl'
    directory.mkdir(exist_ok=True)
    sources, evidence = [], []
    for source, root, multiplier, count in (
            (RTL / 'conv/conv_conv.v', b'conv_conv', b'conv_mul_E2', 9),
            (RTL / 'conv11_16/conv11_conv.v', b'conv11_conv', b'conv11_mul_E2', 1)):
        raw = source.read_bytes()
        raw.decode('gbk')
        new_root = b'fpga_v8_test_' + root
        pattern = rb'(?m)^(module[ \t]+)' + root + rb'(\s*#\()'
        copied, declarations = re.subn(pattern, lambda m: m[1] + new_root + m[2], raw)
        old_instance = multiplier + b' #('
        new_instance = b'fpga_v8_conv_mul_pair #('
        if declarations != 1 or copied.count(old_instance) != count:
            raise RuntimeError('Unexpected core declaration/instance structure: ' + str(source))
        copied = copied.replace(old_instance, new_instance)
        restored = copied.replace(new_instance, old_instance).replace(new_root, root)
        if restored != raw or re.findall(rb'\bmodule\s+(\w+)', copied) != [new_root]:
            raise RuntimeError('Core copy altered more than the authorized names')
        collisions = [str(p) for p in (HERE.parent.parent / 'source').rglob('*.v')
                      if re.search(rb'\bmodule\s+' + new_root + rb'\b', p.read_bytes())]
        if collisions:
            raise RuntimeError('Production test-core-name collision: ' + str(collisions))
        dest = directory / (new_root.decode('ascii') + '.v')
        dest.write_bytes(copied)
        sources.append(dest)
        evidence.append(dict(source=str(source), test_copy=str(dest),
                             source_sha256=sha(source), test_copy_sha256=sha(dest),
                             unique_root=new_root.decode('ascii'), multiplier_instance_sites=count,
                             only_module_names_changed=True, gbk_bytes_preserved=True))
    (directory / 'copy_evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return sources, evidence


def check_mac(directory, config, expected):
    events = [line.split() for line in (directory / 'mac_observed.txt').read_text().splitlines()]
    if any(len(row) != 4 for row in events):
        raise RuntimeError('Malformed MAC stream')
    actual, lasts, invalid_last, unknown = [], [], [], []
    for cycle, valid, last, value in events:
        if valid not in {'0', '1'} or last not in {'0', '1'}:
            unknown.append([cycle, valid, last, value])
        if last == '1':
            lasts.append(len(actual))
            if valid != '1':
                invalid_last.append(int(cycle))
        if valid == '1':
            if any(c in value.lower() for c in 'xz'):
                unknown.append([cycle, valid, last, value])
                actual.append(None)
            else:
                actual.append(int(value, 16))
    mismatches = []
    for index in range(max(len(actual), len(expected))):
        got = actual[index] if index < len(actual) else None
        want = expected[index] if index < len(expected) else None
        if index >= len(actual) or index >= len(expected) or got != want:
            mismatches.append(dict(index=index, got=None if got is None else f'{got:012x}',
                                   expected=None if want is None else f'{want:012x}'))
    wanted_lasts = [(g + 1) * config['width'] - 1
                    for g in range(8 * ((config['co'] + 15) // 16) * config['ib'])]
    result = dict(**config, candidate=str(CANDIDATE), production_sources_unmodified=True,
                  expected_valid_words=len(expected), actual_valid_words=len(actual),
                  mismatch_count=len(mismatches), first_mismatches=mismatches[:12],
                  unknown_count=len(unknown), unknown_events=unknown[:10],
                  expected_last_indices=wanted_lasts, actual_last_indices=lasts,
                  last_without_valid=invalid_last, warnings=warnings(directory),
                  pass_exact=actual == expected and not unknown and not invalid_last and lasts == wanted_lasts)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def run_case(case, delay, cores):
    original_name, *settings = case
    directory, config, expected = make_case(f'pair_{original_name}_d{delay}', *settings)
    config['mul_delay'] = delay
    fixture_hashes = {}
    for filename in ('weights.bin', 'weights.mem', 'data0.mem', 'data1.mem', 'data2.mem', 'expected.mem'):
        baseline = HERE / original_name / filename
        if baseline.read_bytes() != (directory / filename).read_bytes():
            raise RuntimeError('Golden/stimulus differs from the original full stream: ' + str(baseline))
        fixture_hashes[filename] = sha(baseline)
    command([MS / 'vlib.exe', 'work'], directory, 'vlib')
    command([MS / 'vlog.exe', '-quiet', '-work', 'work', VENDOR / 'GTP_GRS.v',
             VENDOR / 'GTP_APM_E2.v', CANDIDATE, *cores, HERE / 'tb_candidate_mac.v'], directory, 'compile')
    text = command([MS / 'vsim.exe', '-c', '-quiet', '-wlf', 'contract.wlf', '-l', 'transcript.log',
                    '-gK=' + str(config['k']), '-gCI=' + str(config['ci']), '-gCO=' + str(config['co']),
                    '-gIB=' + str(config['ib']), '-gUSE11=' + str(config['use11']),
                    '-gW=' + str(config['width']), '-gMUL_DELAY=' + str(delay),
                    'work.fpga_v8_tb_candidate_mac', '-do', 'run -all; quit -f'], directory, 'simulate')
    if 'CANDIDATE_MAC_DONE' not in text:
        raise RuntimeError('Missing complete MAC marker')
    config['original_fixture'] = original_name
    config['fixture_sha256'] = fixture_hashes
    config['fixtures_byte_identical_to_original'] = True
    result = check_mac(directory, config, expected)
    print(config['name'], 'valid', result['actual_valid_words'], '/', result['expected_valid_words'],
          'mismatch', result['mismatch_count'], 'X/Z', result['unknown_count'],
          'last', result['actual_last_indices'], 'PASS', result['pass_exact'], flush=True)
    return result


def main():
    before = verify_sources()
    structure = verify_candidate_structure()
    cores, copies = copy_cores()
    primary = [run_case(case, 4, cores) for case in CASES]
    # Check the unchanged general/dedicated core timing at the supported edges.
    edge = [run_case(case, delay, cores) for delay in (2, 3, 6) for case in (CASES[0], CASES[2])]
    after = verify_sources()
    result = dict(structure=structure, core_copies=copies, primary_cases=primary, edge_cases=edge,
                  primary_expected_words=sum(r['expected_valid_words'] for r in primary),
                  primary_actual_words=sum(r['actual_valid_words'] for r in primary),
                  edge_expected_words=sum(r['expected_valid_words'] for r in edge),
                  edge_actual_words=sum(r['actual_valid_words'] for r in edge),
                  production_source_sha256=after, production_sources_unchanged=before == after,
                  pass_exact=all(r['pass_exact'] for r in primary + edge) and before == after)
    (HERE / 'candidate_pair_mac_results.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['pass_exact']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
