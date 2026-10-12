"""Verify the independently audited PLL56 fresh build and run SRAM --check only.

Writes only a new readiness_evidence_* directory. Large artifacts are hardlinks
used read-only; never set their attributes or write through them. The unchanged
programmer performs its own mandatory complete report hash and violation scan.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from build_later import inherited
from prepare import HERE, ROOT, FROZEN, check


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def assemble(source, review):
    dest = Path(tempfile.mkdtemp(prefix='readiness_evidence_', dir=HERE)).resolve()
    progress = {'status': 'running', 'hardware_operations': 0, 'source_run': str(source),
                'evidence_run': str(dest), 'events': []}

    def emit(stage, **values):
        progress.update(stage=stage, updated=time.strftime('%Y-%m-%d %H:%M:%S'), **values)
        progress['events'].append({'stage': stage, 'time': progress['updated']})
        save(dest / 'readiness_receipt.json', progress)
        print(json.dumps({k: v for k, v in progress.items() if k != 'events'}), flush=True)

    linked = {}

    def link(original, relative, digest=None):
        original = original.resolve(strict=True)
        output = dest / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if digest is None:
            digest = sha(original)
        os.link(original, output)
        require(os.path.samefile(original, output), 'Hardlink identity failed: ' + relative)
        linked[relative] = {'source': str(original), 'sha256': digest,
                            'bytes': original.stat().st_size, 'storage': 'read-only use of hardlink'}

    try:
        emit('verify_audited_scope')
        audit = load(review / 'audit.json')
        receipt = load(source / 'receipt.json')
        require(audit['audit_status'] == 'PASS' and Path(audit['source_run']).resolve() == source,
                'Independent audit is not PASS for this run')
        require(all(v['status'] == 'PASS' for v in audit['checks'].values()), 'Independent check failed')
        require(receipt['status'] == 'built_for_parent_review', 'Source build incomplete')
        require(set(('compile', 'synthesize', 'dev_map', 'strong_pnr', 'routed_phy', 'full_sta', 'bitgen'))
                <= set(receipt['completed_stages']), 'Fresh vendor stages missing')
        pll_scope = check()  # This checks only PLL/clock preparation, not expanded RTL scope.
        manifest = load(source / 'input_sha256.json')
        frozen = load(FROZEN / 'input_sha256.json')
        frozen = {k: v for k, v in frozen.items() if k.startswith(('source/', 'ipcore/'))}
        actual = {p.relative_to(source / 'inputs').as_posix() for p in (source / 'inputs').rglob('*') if p.is_file()}
        require(actual == set(manifest) == set(frozen), 'Actual input inventory mismatch')
        for name, digest in manifest.items():
            require(sha(source / 'inputs' / name) == digest, 'Input changed: ' + name)
        differences = sorted(k for k in manifest if manifest[k] != frozen[k])
        intended = ['source/constraints/clock.fdc', 'source/motion/motion_stream_adapter.v',
                    'source/ov5640/ov5640/ov5640_cdc.v', 'source/top.v']
        require(differences == intended == audit['checks']['actual_input_provenance']['evidence']['differences_vs_frozen'],
                'Expanded audited source scope mismatch')
        for name, digest in [('source/top.v', receipt['candidate_top_sha256']),
                             ('source/motion/motion_stream_adapter.v', receipt['adapter_candidate_sha256']),
                             ('source/ov5640/ov5640/ov5640_cdc.v', receipt['counter_candidate_sha256'])]:
            require(manifest[name] == digest, 'Candidate source binding mismatch: ' + name)
        require(manifest['source/constraints/clock.fdc'] == pll_scope['constraint_sha256']['source/constraints/clock.fdc'],
                'Strict clock constraint binding mismatch')
        project = source / 'work/project.pds'
        require(sha(project) == receipt['runtime_project_sha256'] ==
                audit['checks']['actual_input_provenance']['evidence']['project_sha256'], 'Project changed')
        for raw_path in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project.read_bytes()):
            path = Path(raw_path.decode('ascii')).resolve(strict=True)
            require(source / 'inputs' in path.parents and path.relative_to(source / 'inputs').as_posix() in manifest,
                    'Registered input outside exact manifest')
        emit('verify_simulations_and_vendor_provenance', input_files=len(manifest), intended_changes=differences)
        sims = {}
        for key, hash_key in [('simulation_receipt', 'simulation_receipt_sha256'),
                              ('capture_simulation_receipt', 'capture_simulation_sha256'),
                              ('counter_simulation_receipt', 'counter_simulation_sha256')]:
            path = Path(receipt[key]).resolve(strict=True)
            require(sha(path) == receipt[hash_key], 'Simulation receipt changed: ' + key)
            sim = load(path)
            require(sim['status'] == 'PASS' and sha(path.parent / 'simulation.log') == sim['log_sha256'],
                    'Passing simulation log missing: ' + key)
            for model, digest in sim.get('vendor_models', {}).items():
                require(sha(model) == digest, 'Simulation vendor model changed')
            sims[key] = {'path': str(path), 'sha256': receipt[hash_key], 'evidence': sim}
            link(path, 'simulations/' + key + '.json', receipt[hash_key])
            link(path.parent / 'simulation.log', 'simulations/' + key + '.log', sim['log_sha256'])
        require(sims['simulation_receipt']['evidence']['candidate_top_sha256'] == manifest['source/top.v'] and
                sims['simulation_receipt']['evidence']['emitted_transactions'] == 1584 and
                sims['capture_simulation_receipt']['evidence']['candidate_sha256'] == manifest[intended[1]] and
                sims['counter_simulation_receipt']['evidence']['candidate_sha256'] == manifest[intended[2]],
                'Simulation candidate binding mismatch')
        validators = inherited()
        for name, digest in receipt['log_sha256'].items():
            path = source / name
            require(sha(path) == digest, 'Vendor log changed: ' + name)
            text = path.read_bytes().decode('gb18030', errors='replace')
            require(not re.search(validators.VENDOR_ERROR, text, re.M | re.I), 'Vendor error: ' + name)
            link(path, 'original/' + name, digest)
        for stage, operation, input_name in [('strong_pnr', 'pnr', 'work/device_map/top_map.adf'),
                                            ('full_sta', 'report_timing', 'work/place_route/top_pnr.adf'),
                                            ('bitgen', 'gen_bit_stream', 'work/place_route/top_pnr.adf')]:
            text = (source / (stage + '.log')).read_bytes().decode('gb18030', errors='replace')
            require(re.search(r'Executing : ' + operation + r'[^\n]*' + re.escape((source / input_name).as_posix()) +
                              r'[^\n]*successfully\.', text), 'Exact successful vendor input missing: ' + stage)
            require((source / input_name).as_posix() in (source / (stage + '.tcl')).read_text(), 'Tcl input mismatch')
            link(source / (stage + '.tcl'), 'original/' + stage + '.tcl')
        hashes = audit['checks']['artifact_hashes']['evidence']
        for relative, hash_key in [('top.sbit', 'bit_sha256'), ('work/place_route/top_pnr.adf', 'route_sha256'),
                                   ('work/device_map/top_map.adf', 'mapped_sha256'),
                                   ('work/synthesize/top_syn.adf', 'synthesized_sha256'),
                                   ('work/device_map/top.pcf', 'physical_constraints_sha256')]:
            require(sha(source / relative) == hashes[hash_key] == receipt[hash_key], 'Artifact changed: ' + relative)
        bits = list((source / 'bitgen').rglob('*.sbit'))
        require(len(bits) == 1 and sha(bits[0]) == hashes['bit_sha256'], 'Actual bitgen output mismatch')
        emit('verify_pins_PHY_RAM_and_strict_STA')
        pin_report = source / 'work/place_route/top_prr.prt'
        pins = validators.pinmap(pin_report)
        require(len(pins) == 112 and pins == validators.pinmap(FROZEN / 'routed/top_prr.prt'), 'Actual pins differ')
        pin = load(source / 'pin_audit.json')
        require(pin['identical'] and pin['ports'] == 112 and pin['report_sha256'] == sha(pin_report), 'Pin proof mismatch')
        physical = validators.phy(source / 'routed_phy.txt')
        require(physical == validators.phy(FROZEN / 'routed_phy.txt'), 'Dedicated PHY differs')
        phy = load(source / 'phy_audit.json')
        require(phy['identical'] and phy['actual'] == json.loads(json.dumps(physical)) and
                phy['route_sha256'] == hashes['route_sha256'], 'PHY proof mismatch')
        strict = load(review / 'strict_full_STA.json')
        require(strict['status'] == 'PASS' and strict['violated_paths'] == 0 and len(strict['rows']) == 126 and
                strict['report_sha256'] == hashes['timing_report_sha256'] and
                (source / 'final_sta/report_timing/top.rtr').stat().st_size == strict['full_report_bytes'], 'Independent STA mismatch')
        require(strict['rows'] == load(source / 'strict_timing.json')['rows'], 'Strict STA rows changed')
        clocks = load(source / 'clock_audit.json')
        require(clocks == audit['checks']['strict_CAM34_clocks']['evidence'] and clocks['status'] == 'PASS' and
                all(clocks['clocks'][f'cmos{i}_pclk']['period'] == 17.857 for i in (3, 4)), 'CAM3/4 clocks mismatch')
        old = load(source / 'motion_resource_proof.json')
        utilization = source / 'work/synthesize/apm_drm_lutram_utilization.log'
        require(old['evidence_sha256'] == sha(utilization) and old['mapped_sha256'] == hashes['mapped_sha256'] and
                old['synthesized_sha256'] == hashes['synthesized_sha256'] and old['route_sha256'] == hashes['route_sha256'],
                'Fresh resource bindings mismatch')
        raw, routed = utilization.read_bytes(), (source / 'routed_phy.txt').read_bytes()
        histories = []
        for row in old['histories']:
            require(row['evidence'].encode('ascii') in raw and row['width'] == 8 and row['mode'] == 'read_first', 'RAM quote mismatch')
            for bank in row['routed_banks']:
                match = re.search(rb'\(INSTANNOTATE\s+\(INSTREF\s+\\?' + re.escape(bank['instance'].encode()) +
                                  rb'\s*\)\s*\(PLACE\s+impl_drm\s+\(DEVINSTREF\s+DRM\s+\(SITEREF\s+(\d+)\s+(\d+)', routed)
                require(match and [int(x) for x in match.groups()] == bank['site'], 'Actual routed RAM bank mismatch')
            histories.append(dict(row, instance=row['instance'].removesuffix('/history'), depth=19200,
                                  bram_instances=[b['instance'] for b in row['routed_banks']], evidence=[
                                      {'file': 'work/synthesize/apm_drm_lutram_utilization.log', 'sha256': old['evidence_sha256'], 'quote': row['evidence']},
                                      {'file': 'inputs/source/motion/block_motion_detector.v', 'sha256': manifest['source/motion/block_motion_detector.v'],
                                       'quote': 'reg [7:0] history [0:TOTAL_SAMPLES-1];'}]))
        require(len(histories) == 4 and sum(len(h['bram_instances']) for h in histories) == 32, '32-bank scope missing')
        counter = audit['checks']['actual_counter_mapping']['evidence']
        require(counter['routed_counter_FFs'] == counter['synthesized_counter_FFs'] == 128 and
                counter['connected_counter_CE_pins'] == 0 and counter['LCE_EN'] == 'FALSE' and
                sha(source / 'routed_phy.v') == counter['routed_netlist_sha256'], 'Counter mapping binding mismatch')
        emit('assemble_generic_programmer_contract', full_STA_rows=126, full_STA_bytes=strict['full_report_bytes'],
             motion_banks=32, counter_FFs=128)
        for name, digest in manifest.items():
            link(source / 'inputs' / name, 'inputs/' + name, digest)
        for original, relative, digest in [(source / 'top.sbit', 'top.sbit', hashes['bit_sha256']),
                (source / 'work/place_route/top_pnr.adf', 'routed/top_pnr.adf', hashes['route_sha256']),
                (pin_report, 'routed/top_prr.prt', pin['report_sha256']),
                (source / 'final_sta/report_timing/top.rtr', 'final_sta/report_timing/top.rtr', strict['report_sha256']),
                (source / 'work/device_map/top_map.adf', 'work/device_map/top_map.adf', hashes['mapped_sha256']),
                (source / 'work/device_map/top.pcf', 'work/device_map/top.pcf', hashes['physical_constraints_sha256']),
                (source / 'work/synthesize/top_syn.adf', 'work/synthesize/top_syn.adf', hashes['synthesized_sha256']),
                (utilization, 'work/synthesize/apm_drm_lutram_utilization.log', old['evidence_sha256'])]:
            link(original, relative, digest)
        for name in ['receipt.json', 'input_sha256.json', 'motion_resource_proof.json', 'counter_mapping_proof.json',
                     'clock_audit.json', 'strict_timing.json', 'input_diff_proof.json', 'routed_phy.txt', 'routed_phy.v']:
            link(source / name, 'original/' + name)
        link(project, 'original/project.pds', receipt['runtime_project_sha256'])
        link(review / 'audit.json', 'independent/audit.json')
        link(review / 'strict_full_STA.json', 'independent/strict_full_STA.json')
        save(dest / 'input_sha256.json', manifest)
        resource = dict(required_histories=4, bits_per_history=19200 * 8, histories=histories,
                        mapped_sha256=old['mapped_sha256'], synthesized_sha256=old['synthesized_sha256'],
                        route_sha256=old['route_sha256'], reviewer='PLL56 adapter: direct verification of independently audited fresh map/route',
                        review_kind='Automated artifact attribution; runtime acceptance pending')
        save(dest / 'resource_review.json', resource)
        validators.W = dest / 'work'
        validators.resources(dest)  # Unmodified inherited geometry/hash/quote gate.
        save(dest / 'pin_audit.json', pin)
        save(dest / 'phy_audit.json', phy)
        save(dest / 'final_sta_proof.json', dict(route_sha256=hashes['route_sha256'], report_sha256=strict['report_sha256'],
                                                rows=strict['rows'], full_report_violations=0, independent_review=str(review)))
        save(dest / 'assembly_provenance.json', dict(source_run=str(source), adapter_sha256=sha(Path(__file__)),
             source_receipt_sha256=sha(source / 'receipt.json'), independent_audit_sha256=sha(review / 'audit.json'),
             scope=differences, source_bindings=manifest, linked=linked, simulations=sims,
             vendor_completed_stages=receipt['completed_stages'], counter_mapping=counter,
             build_kind='Fresh isolated compile, synthesis, device map, placement/route, final STA and bitgen',
             hardware_operations=0, runtime_acceptance='pending'))
        provenance = dict(bit_sha256=hashes['bit_sha256'], route_sha256=hashes['route_sha256'],
                          report_sha256=strict['report_sha256'], mapped_sha256=hashes['mapped_sha256'],
                          pcf_sha256=hashes['physical_constraints_sha256'], source_run=str(source),
                          assembly_provenance_sha256=sha(dest / 'assembly_provenance.json'))
        for key, name in [('resource_proof_sha256', 'resource_proof.json'), ('pin_proof_sha256', 'pin_audit.json'),
                          ('phy_proof_sha256', 'phy_audit.json'), ('input_manifest_sha256', 'input_sha256.json')]:
            provenance[key] = sha(dest / name)
        save(dest / 'bit_provenance.json', provenance)
        status = dict(stage='complete', status='complete', run=str(dest), bit=str(dest / 'top.sbit'),
                      bit_sha256=hashes['bit_sha256'], route_sha256=hashes['route_sha256'], report_sha256=strict['report_sha256'],
                      source_run=str(source), scope=differences, origin='Verified assembly of completed fresh PLL56 build',
                      assembly_provenance_sha256=sha(dest / 'assembly_provenance.json'),
                      runtime_acceptance='pending', hardware_programming='not_performed', flash='untouched')
        save(dest / 'status.json', status)
        programmer = ROOT / 'project/tools/program_100h_motion.py'
        programmer_hash = sha(programmer)
        command = [sys.executable, '-B', str(programmer), '--mode', 'sram', '--check', '--bit', status['bit'],
                   '--build-status', str(dest / 'status.json'), '--manifest', str(dest / 'status.json'),
                   '--log-dir', str(dest / 'checks')]
        save(dest / 'exact_check_command.json', {'argv': command, 'command': subprocess.list2cmdline(command),
                                               'programmer_sha256': programmer_hash})
        emit('unchanged_programmer_check_full_report_hash_and_scan', exact_command=subprocess.list2cmdline(command))
        with (dest / 'readiness_check.stdout.txt').open('wb') as output:
            proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, shell=False)
            emit('programmer_check_running', check_pid=proc.pid)
            while proc.poll() is None:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    emit('programmer_check_running', check_pid=proc.pid, stdout_bytes=(dest / 'readiness_check.stdout.txt').stat().st_size)
        require(sha(programmer) == programmer_hash, 'Programmer changed during check')
        checks = list((dest / 'checks').glob('run_*/receipt.json'))
        require(len(checks) == 1, 'Unique programmer receipt missing')
        result = load(checks[0])
        require(proc.returncode == 0 and result['status'] == 'validated_only' and result['check_only'] is True and
                result['mode'] == 'sram' and result['bit_sha256'] == hashes['bit_sha256'],
                'Unchanged programmer check blocked: ' + str(result.get('error')))
        emit('ready_for_parent_SRAM_runtime_validation', status='validated_only', check_exit_code=proc.returncode,
             programmer_receipt=str(checks[0]), programmer_receipt_sha256=sha(checks[0]), programmer_sha256=programmer_hash)
        (dest / 'READINESS.md').write_text('PLL56 readiness: unchanged programmer SRAM --check exited 0, validated_only.\n\n'
            'Build completion describes completed isolated compile/synthesis/map/route/STA/bitgen. Four intended input changes '
            'are recorded explicitly in status and assembly provenance. All 694 inputs are bound to the exact manifest. '
            'The independent audit scanned 126 STA rows and the full report; the unchanged programmer additionally hashed '
            'and scanned the actual hardlinked report. Artifacts are shared hardlinks and must be used read-only.\n\n'
            'No vendor tools, SSH, hardware programming, Flash or runtime acceptance were performed. Parent owns future SRAM tests.\n\n'
            'Receipt: ' + str(checks[0]) + '\n\nExact command:\n\n```text\n' + subprocess.list2cmdline(command) + '\n```\n', encoding='utf-8')
        return dest
    except Exception as error:
        emit('blocked', status='blocked', error=str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, default=HERE / 'build_counter_9caopnhe')
    parser.add_argument('--independent-review', type=Path, default=HERE / 'independent_review_zn_cfywi')
    args = parser.parse_args()
    assemble(args.source_run.resolve(strict=True), args.independent_review.resolve(strict=True))
