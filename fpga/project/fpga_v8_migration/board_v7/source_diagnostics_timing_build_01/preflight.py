"""Isolated byte-preserving preparation. No PDS invocation here."""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
BASE = BOARD / 'source_diagnostics_route_02'
FROZEN = BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json'
LEASE = BOARD / 'capture_lease_prefix_timing_candidate'
FROZEN_SHA = '45e3b1d5ed79ac8b0782f64a9f12f1ad8a463306f4688a864269534e7470fe89'
CANDIDATE_SHA = '0461af04c40f6c3bbdea0367d084fa6e4d33647c17bede58ea341323779017ed'
OLD = b'fpga_v8_capture_lease_tc04'
NEW = b'fpga_v8_capture_lease_prefix'
TOP = 'rtl/v7_sdt_top.v'

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    return json.loads(Path(path).read_bytes())

def save(name, value):
    (HERE / name).write_bytes((json.dumps(value, indent=2, ensure_ascii=True) + '\n').encode('ascii'))

def frozen_guard():
    require(sha(FROZEN) == FROZEN_SHA, 'exact09 manifest hash drift')
    hashes = load(FROZEN)
    checked = {}
    for name, expected in hashes.items():
        if name.startswith(('rtl\\', 'inputs\\')):
            path = BASE / name
            require(path.is_file() and sha(path) == expected, 'Frozen input drift: ' + name)
            checked[name.replace('\\', '/')] = expected
    require(bool(checked), 'Empty frozen inventory')
    return checked

def lease_gate(hashes):
    results = load(LEASE / 'evidence/results.json')
    binding = load(LEASE / 'evidence/frozen_binding.json')
    require(binding['frozen_manifest_sha256'] == FROZEN_SHA, 'Lease frozen manifest mismatch')
    for key, hashkey in [('source', 'source_sha256'), ('top', 'top_sha256')]:
        path = Path(binding[key])
        require(path.is_relative_to(BASE), 'Lease binding outside route02')
        rel = path.relative_to(BASE).as_posix()
        require(sha(path) == binding[hashkey] == hashes[rel], 'Lease binding drift: ' + rel)
    checks = [('candidate/fpga_v8_capture_lease_prefix.v', 'candidate_sha256'),
              ('original/fpga_v8_capture_lease_tc04.v', 'original_sha256'),
              ('tb_lease_prefix.sv', 'tb_sha256'), ('evidence/candidate.diff', 'diff_sha256')]
    for name, key in checks:
        require(sha(LEASE / name) == results[key], 'Lease artifact drift: ' + name)
    require(results['candidate_sha256'] == CANDIDATE_SHA, 'Unexpected candidate')
    require(results['original_sha256'] == binding['source_sha256'], 'Original binding mismatch')
    require(results['pass_all'] is True and results['protected_unchanged'] is True
            and results['negative_control_detected'] is True, 'Lease aggregate gate failed')
    expected = {'host1_bad0', 'host0_bad0'} | {'host1_bad' + str(i) for i in range(1, 8)}
    require(set(results['results']) == expected, 'Lease test set incomplete')
    cycles = 0
    for name, marker in results['results'].items():
        log = (LEASE / ('evidence/' + name + '.log')).read_bytes()
        require(marker.encode('ascii') in log and 'LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS' in marker,
                'Missing real PASS log: ' + name)
        require(re.search(rb'Errors:\s*0\b', log) is not None
                and re.search(rb'\*\*\s+(?:Error|Fatal):', log) is None, 'Lease log error: ' + name)
        cycles += int(re.search(r'cycles=(\d+)', marker).group(1))
    require(cycles == 319624, 'Lease cycle coverage mismatch')
    require(all(x['returncode'] == 0 for x in results['commands']), 'Lease command failed')
    receipt = {'status': 'PASS', 'tests': 9, 'cycles': cycles, 'hashes': {}}
    for p in [LEASE / 'evidence/results.json', LEASE / 'evidence/frozen_binding.json'] + [LEASE / n for n, _ in checks] + [LEASE / ('evidence/' + n + '.log') for n in sorted(expected)]:
        receipt['hashes'][str(p)] = sha(p)
    return receipt

def strip_comments(data):
    return re.sub(rb'//[^\r\n]*|/\*.*?\*/', b'', data, flags=re.S)

def source_scan(paths):
    modules = {}
    instances = []
    for name in paths:
        if not name.endswith(('.v', '.vp')):
            continue
        data = strip_comments((HERE / name).read_bytes())
        for m in re.findall(rb'\bmodule\s+(\w+)', data):
            modules.setdefault(m.decode('ascii'), []).append(name)
        if b'u_v8_capture_lease' in data:
            instances.append(name)
    duplicate = {k: v for k, v in modules.items() if len(v) > 1}
    require(not duplicate, 'Duplicate registered modules: ' + repr(duplicate))
    require(instances == [TOP], 'Actual lease instance must be unique: ' + repr(instances))
    require(modules.get(NEW.decode()) == ['rtl/fpga_v8_capture_lease_prefix.v'], 'Candidate definition not unique')
    require('v7_sdt_top' in modules, 'Missing original top name')
    return {'registered_module_count': len(modules), 'duplicates': duplicate,
            'lease_parent': TOP, 'lease_instance_count': 1, 'top': 'v7_sdt_top'}

def prepare():
    require(not (HERE / 'manifest.json').exists(), 'Already prepared; use --verify')
    hashes = frozen_guard()
    lease = lease_gate(hashes)
    project_path = BASE / 'standard_flow_exact09.pds'
    project = project_path.read_bytes()
    registered = [p.decode('ascii') for p in re.findall(rb'\(_file "((?:rtl|inputs)/[^"\n]+)"', project)]
    require(TOP in registered and 'rtl/fpga_v8_cooperative_top_v2_rfg01.v' not in registered,
            'Actual parent registration changed')
    # Copy only frozen RTL/input assets (about 14 MB), never compile/route DBs.
    # FDCs and embedded PDSs are deliberately excluded; no constraint is guessed.
    copied = {}
    for name, expected in hashes.items():
        if Path(name).suffix.lower() in {'.fdc', '.pds'}:
            continue
        out = HERE / name
        require(not out.exists(), 'Refuse overwrite: ' + name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((BASE / name).read_bytes())
        require(sha(out) == expected, 'Copy hash mismatch')
        copied[name] = expected
    old_top = (HERE / TOP).read_bytes()
    pattern = rb'\b' + OLD + rb'(?=\s*#\s*\()'
    require(len(re.findall(pattern, strip_comments(old_top))) == 1
            and strip_comments(old_top).count(b'u_v8_capture_lease') == 1, 'Ambiguous live lease binding')
    new_top, count = re.subn(pattern, NEW, old_top)
    require(count == 1 and new_top.replace(NEW, OLD) == old_top, 'Unexpected parent edit')
    (HERE / TOP).write_bytes(new_top)
    candidate_name = 'rtl/fpga_v8_capture_lease_prefix.v'
    (HERE / candidate_name).write_bytes((LEASE / 'candidate/fpga_v8_capture_lease_prefix.v').read_bytes())
    require(project.count(b'"rtl/fpga_v8_capture_lease_tc04.v"') == 1, 'Ambiguous source registration')
    project = project.replace(b'"rtl/fpga_v8_capture_lease_tc04.v"', b'"rtl/fpga_v8_capture_lease_prefix.v"')
    # Leave original six constraint registrations as explicit missing placeholders.
    project = project.replace(b'physical_constraints_exact_09/', b'constraints_pending/')
    require(b'(_string "v7_sdt_top")' in project, 'Top option changed')
    (HERE / 'project_template.pds').write_bytes(project)
    registered = [candidate_name if p == 'rtl/fpga_v8_capture_lease_tc04.v' else p for p in registered]
    scan = source_scan(registered)
    diff = ''.join(difflib.unified_diff(old_top.decode('latin1').splitlines(True),
                                      new_top.decode('latin1').splitlines(True),
                                      fromfile='route02/' + TOP, tofile='isolated/' + TOP))
    (HERE / 'lease_binding.diff').write_bytes(diff.encode('latin1'))
    copied[TOP] = sha(HERE / TOP)
    copied[candidate_name] = sha(HERE / candidate_name)
    manifest = {'schema': 1, 'mode': 'PREPARATION_ONLY_NO_PDS', 'top': 'v7_sdt_top',
                'baseline': str(BASE), 'frozen_manifest': str(FROZEN), 'frozen_sha256': FROZEN_SHA,
                'template_source_sha256': sha(project_path), 'local_hashes': copied,
                'template_sha256': sha(HERE / 'project_template.pds'), 'registered_sources': registered,
                'binding_scan': scan, 'lease_gate': lease,
                'changes': [{'path': TOP, 'before': hashes[TOP], 'after': copied[TOP],
                             'edit': 'single actual u_v8_capture_lease module type; all parameters/ports unchanged'},
                            {'path': candidate_name, 'sha256': CANDIDATE_SHA,
                             'registration_replaces': 'rtl/fpga_v8_capture_lease_tc04.v'}],
                'pending': ['camera_read_decode: results/binding adapter and all-PASS verification',
                            'capture_control_decode: results/binding adapter and all-PASS verification',
                            'main-session qualified constraint-agent import with input-bound certificate',
                            'integrated elaboration/simulation and physical timing',
                            'ten mailbox/reset/IO acceptance groups before any bitstream'],
                'cdc_candidates_imported': False, 'bitstream_allowed': False,
                'preserved_by_byte_identity': 'six-camera RAW/motion parameters, clocks, IO, newbus cycles except lease type token'}
    save('manifest.json', manifest)
    frozen_guard()
    verify()

def verify():
    manifest = load(HERE / 'manifest.json')
    hashes = frozen_guard()
    require(lease_gate(hashes) == manifest['lease_gate'], 'Lease evidence drift')
    for name, expected in manifest['local_hashes'].items():
        require(sha(HERE / name) == expected, 'Local source drift: ' + name)
    require(sha(HERE / 'project_template.pds') == manifest['template_sha256'], 'Template drift')
    require(sha(BASE / 'standard_flow_exact09.pds') == manifest['template_source_sha256'], 'Baseline project drift')
    scan = source_scan(manifest['registered_sources'])
    require(scan == manifest['binding_scan'], 'Binding scan drift')
    if 'decode_candidates_gate' in manifest:
        from integrate_candidates import audit
        require(audit() == manifest['decode_candidates_gate'], 'Decode candidate audit drift')
    old_top = (BASE / TOP).read_bytes()
    new_top = (HERE / TOP).read_bytes()
    require(new_top.replace(NEW, OLD) == old_top, 'Top byte identity outside binding failed')
    controller = load(HERE / 'controller_status.json') if (HERE / 'controller_status.json').exists() else {}
    signoff = load(HERE / 'evidence/signoff.json') if (HERE / 'evidence/signoff.json').exists() else {}
    save('preflight_result.json', {'preparation_pass': True, 'candidate_integration_pass': 'decode_candidates_gate' in manifest,
                                 'physical_signoff_pass': signoff.get('passed') is True,
                                 'controller_phase': controller.get('phase', 'NOT_STARTED'),
                                 'build_ready': 'decode_candidates_gate' in manifest,
                                 'baseline_files_checked': len(hashes),
                                 'local_files_checked': len(manifest['local_hashes']),
                                 'binding': scan, 'pending': manifest['pending'],
                                 'pds_started': (HERE / 'evidence/compile_launch.json').exists()})
    status = (
        '# \u72ec\u7acb\u6574\u673a\u65f6\u5e8f\u96c6\u6210\u51c6\u5907\u72b6\u6001\n\n'
        '\u51c6\u5907 PASS\uff1b\u6574\u673a\u6784\u5efa pending\u3002\u672a\u8fd0\u884c PDS\uff0c\u672a\u751f\u6210 bitstream\u3002\n\n'
        '\u5b9e\u9645\u57fa\u7ebf\uff1aroute02/standard_flow_exact09.pds + exact09/input_hashes.json\u3002\n'
        '\u5b9e\u9645\u7f16\u8bd1 parent\uff1artl/v7_sdt_top.v\uff0ctop name v7_sdt_top\u3002\n'
        '\u552f\u4e00\u5b9e\u4f8b u_v8_capture_lease\uff1afpga_v8_capture_lease_tc04 -> fpga_v8_capture_lease_prefix\u3002\n'
        '\u5019\u9009 SHA256: ' + CANDIDATE_SHA + '\n'
        '\u5df2\u8bfb\u53d6 results.json/frozen_binding.json\uff0c\u9a8c\u8bc1\u5019\u9009\u3001\u539f\u6a21\u5757\u3001parent\u3001TB\u3001diff hash\u53ca\u4e5d\u7ec4\u5b9e\u9645 PASS \u65e5\u5fd7\uff08319624 \u62cd\uff09\u3002\n\n'
        '\u7ed1\u5b9a\u98ce\u9669\uff1acooperative_top \u62a5\u544a\u6307\u5411\u7684 parent \u4e0d\u662f\u8be5 PDS \u767b\u8bb0\u6e90\uff1b\u4ec5\u6539\u5b83\u4e0d\u4f1a\u8fdb\u5165\u5b9e\u9645\u6784\u5efa\u3002\n'
        '\u672c\u7248\u4ec5\u4fee\u6539\u5b9e\u9645 v7_sdt_top \u4e00\u5904 module type \u5b57\u8282\u548c\u6e90\u767b\u8bb0\uff1b\u6bcf\u6b21 verify \u90fd\u68c0\u67e5\u5176\u4f59 top \u5b57\u8282\u5b8c\u5168\u76f8\u540c\u3002\n'
        '\u516d\u76f8\u673a RAW/motion \u53c2\u6570\u3001\u65f6\u949f\u3001IO \u53ca newbus \u5468\u671f\u4fdd\u6301\u539f\u7248\u3002\u672a\u6df7\u5165 CDC \u4fee\u6b63\u5019\u9009\u3002\n'
        '\u672a\u767b\u8bb0\u7684\u65e7 lease/cooperative \u526f\u672c\u4ec5\u4f5c\u51bb\u7ed3\u8ffd\u6eaf\uff0c\u4e0d\u53c2\u4e0e\u7f16\u8bd1\u3002\n\n'
        '\u672a\u6ee1\u8db3\u95e8\u69db\uff1a\n'
        '- camera_read_decode \u548c capture_control_decode \u4ecd pending\uff1b\u672a\u5b9e\u73b0\u6216\u81ea\u52a8\u63a5\u53d7\u5b83\u4eec\u7684\u8bc1\u636e\u683c\u5f0f\u3002\u4e3b\u4f1a\u8bdd\u5fc5\u987b\u52a0\u5165\u5404\u81ea results/binding/hash \u4e0e\u5168\u6d4b\u8bd5 PASS \u9002\u914d\u540e\u624d\u80fd\u66ff\u6362\u3002\n'
        '- \u4e3b\u4f1a\u8bdd\u5bfc\u5165\u7ea6\u675f\u4ee3\u7406\u5408\u683c\u6a21\u677f\u548c\u8bc1\u636e\uff1b\u5f53\u524d constraints_pending \u53ea\u662f\u7f3a\u5931\u8def\u5f84\uff0c\u6ca1\u6709\u751f\u6210\u731c\u6d4b FDC\u3002\n'
        '- \u6574\u673a\u7f16\u8bd1/\u4eff\u771f/\u7269\u7406\u65f6\u5e8f\u672a\u9a8c\u8bc1\uff0c\u4e0d\u80fd\u5ba3\u79f0 WNS \u6539\u5584\u3002\n'
        '- \u5341\u7ec4 mailbox/reset/IO \u9a8c\u6536\u524d\u7981\u6b62 bitstream\uff1brun_pds.py \u4e0d\u63d0\u4f9b bit \u9636\u6bb5\u3002\n\n'
        '\u672c\u5730\u547d\u4ee4\uff1apython preflight.py --verify\u3002\n'
        'run_pds.py --stage compile|synthesize|dev_map|pnr \u4e3a\u5b98\u65b9 stage \u5165\u53e3\u9aa8\u67b6\uff0c\u5f53\u524d\u4f1a\u5728\u542f\u52a8\u524d\u963b\u65ad\u3002\n'
        '\u4e3b\u4f1a\u8bdd\u9700\u5b8c\u6210\u9002\u914d\u548c\u7ea6\u675f\u5bfc\u5165\uff0c\u66f4\u65b0 preflight/manifest\uff0c\u5e76\u7ed9\u51fa\u7ed1\u5b9a project/manifest/evidence hash \u7684 build_release.json\u3002\n'
        '\u5165\u53e3\u4f7f\u7528\u5168\u5c40 mutex + GUI/shell \u8fdb\u7a0b\u68c0\u67e5\uff0c\u9636\u6bb5\u524d\u540e\u68c0\u67e5 hash\uff0c\u8981\u6c42\u771f\u5b9e\u975e\u7a7a ADF/native XML DB/\u663e\u5f0f\u96f6 errors\u3002\n'
        '\u5168\u5c40 mutex \u4ec5\u80fd\u4e92\u65a5\u540c\u534f\u8bae runner\uff1b\u975e\u534f\u4f5c GUI \u4ecd\u9700\u4e3b\u4f1a\u8bdd\u7edf\u4e00\u8c03\u5ea6\u3002\n'
    )
    (HERE / 'STATUS.md').write_bytes(status.encode('gbk'))
    if 'decode_candidates_gate' in manifest:
        current = ('# \u5b9e\u9645\u5019\u9009\u96c6\u6210\u72b6\u6001\n\n'
                   '\u4e09\u9879\u5019\u9009\u5168\u90e8\u5df2\u6838\u9a8c\u5e76\u5b9e\u9645\u96c6\u6210\u3002\u7269\u7406\u7b7e\u6838\u5c1a\u672a\u901a\u8fc7\u3002\n'
                   'lease: rtl/v7_sdt_top.v \u552f\u4e00 u_v8_capture_lease -> fpga_v8_capture_lease_prefix; 9/319624 PASS\u3002\n'
                   'camera: inputs/source/ov5640/ov5640_reg.v; 6/130140 PASS; CSV \u5168\u8f93\u51fa\u9010\u884c\u5dee\u5f02 0\u3002\n'
                   'control: rtl/fpga_v8_capture_control_axil_arm_v2.v; 18/861948/49 signals + 26488 cycles/499 ops PASS\u3002\n'
                   '\u53ea\u6709\u4e0a\u8ff0\u4e09\u9879\u6e90\u5dee\u5f02\uff0c\u5176\u4f59\u51bb\u7ed3\u8f93\u5165\u9010\u5b57\u8282\u4fdd\u6301\u3002\u65e0 CDC \u4fee\u6b63\u5019\u9009\u3002\n'
                   '\u7ea6\u675f exact11 \u4ec5\u4f5c\u5019\u9009\uff1b\u65b0 compile/syn graph \u5fc5\u987b\u91cd\u65b0\u63a8\u5bfc\u5b8c\u6574\u53f6\u8282\u70b9\u3001U-B\u30011320 mapping\u3002\n'
                   '\u65e0\u7269\u7406 graph coverage PASS \u4e0d\u5f97 PNR\uff1b\u65e0\u5341\u7ec4/IO112/HSST/motion32/mailbox1320 SlowFast/reset32/sync \u5b9e\u6d4b PASS \u4e0d\u5f97 bit\u3002\n'
                   '\u5b9e\u9645\u9636\u6bb5\u4e0e\u542f\u52a8\u65e5\u5fd7\u89c1 controller_status.json \u548c evidence/\u3002\u65e0 remote/program\u3002\n')
        (HERE / 'STATUS.md').write_bytes(current.encode('gbk'))
    print('CANDIDATE PREFLIGHT PASS; PHYSICAL SIGNOFF ' + ('PASS' if signoff.get('passed') is True else 'UNPROVEN') + '; NO BITSTREAM')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    prepare() if args.prepare else verify()
