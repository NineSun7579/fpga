"""Isolated recovery of build_ny4i9z_e; never accepts failing final STA."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from build_later import ARCH, PDS, idle, inherited
from prepare import HERE, FROZEN, check, save

FAILED = HERE / 'build_ny4i9z_e'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def analyze(report):
    """Stream the large report and retain every violated path, with its corner."""
    paths, rows, current, section = [], [], {}, None
    with report.open('rb') as stream:
        for raw in stream:
            line = raw.strip().decode('ascii', errors='replace')
            match = re.search(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\)', line)
            if match:
                section = match.groups()
            match = re.fullmatch(r'(\w+)\s+(\w+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)', line)
            if match and section:
                a, b, slack, total, failing, endpoints = match.groups()
                rows.append(dict(section=section, launch=a, capture=b, slack=float(slack),
                                 total=float(total), failing=int(failing), endpoints=int(endpoints)))
            for token in ('Startpoint', 'Endpoint', 'Path Group', 'Path Type'):
                if line.startswith(token) and ':' in line:
                    if token == 'Startpoint':
                        current = {}
                    current[token] = line.split(':', 1)[1].strip()
            if line.startswith('Slack (VIOLATED)'):
                paths.append(dict(current, slack=float(line.split()[-1])))
    return dict(report_sha256=sha(report), summary_rows=rows, violated_paths=paths)


def preflight():
    proof = check()
    receipt = json.loads((FAILED / 'receipt.json').read_bytes())
    if receipt.get('status') != 'failed' or receipt.get('stage') != 'full_sta':
        raise RuntimeError('Parent build must have completed at full_sta failure')
    if (HERE / 'build.lock').exists():
        raise RuntimeError('Parent build still owns build.lock')
    expected = json.loads((FAILED / 'input_sha256.json').read_bytes())
    for name, digest in expected.items():
        if sha(FAILED / 'inputs' / name) != digest:
            raise RuntimeError('Failed-build input changed: ' + name)
    if sha(FAILED / 'work/project.pds') != receipt['runtime_project_sha256']:
        raise RuntimeError('Failed-build project changed')
    if sha(FAILED / 'inputs/source/top.v') != proof['candidate_top_sha256']:
        raise RuntimeError('Candidate identity mismatch')
    for name, digest in receipt['log_sha256'].items():
        if sha(FAILED / name) != digest:
            raise RuntimeError('Parent stage log changed: ' + name)
    idle()
    return proof, expected


def run(vendor_help=False):
    # Share the parent's candidate lock; no stale-lock deletion or parallel PDS.
    lock = HERE / 'build.lock'
    with lock.open('x') as stream:
        stream.write('timing_recovery')
    dest = None
    try:
        # preflight's lock guard was already checked before acquiring ownership.
        proof = check()
        idle()
        dest = Path(tempfile.mkdtemp(prefix='recovery_', dir=HERE))
        receipt = dict(status='running', parent=str(FAILED), run=str(dest),
                       script_sha256=sha(Path(__file__)), started=time.strftime('%Y-%m-%d %H:%M:%S'),
                       candidate=proof)
        save(dest / 'receipt.json', receipt)
        validators = inherited()
        expected = json.loads((FAILED / 'input_sha256.json').read_bytes())
        protected = {str(FAILED / 'inputs' / name): digest for name, digest in expected.items()}
        for relative in ['work/project.pds', 'work/device_map/top_map.adf', 'work/device_map/top.pcf',
                         'work/synthesize/top_syn.adf', 'work/place_route/top_pnr.adf',
                         'work/place_route/top_plc.adf', 'strong_pnr.tcl', 'receipt.json']:
            protected[str(FAILED / relative)] = sha(FAILED / relative)
        save(dest / 'protected_sha256.json', protected)

        def verify():
            check()
            for name, digest in protected.items():
                if sha(Path(name)) != digest:
                    raise RuntimeError('Protected parent artifact changed: ' + name)
            for name, digest in expected.items():
                if (dest / 'inputs').exists() and sha(dest / 'inputs' / name) != digest:
                    raise RuntimeError('Private input changed: ' + name)

        def action(name, body, cwd):
            verify()
            (dest / (name + '.tasklist.csv')).write_bytes(idle())
            cwd.mkdir(parents=True, exist_ok=True)
            script = dest / (name + '.tcl')
            script.write_text(ARCH + body, encoding='ascii')
            command = [str(PDS), '-file', str(script), '-work_dir', str(cwd), '-project_name', name]
            receipt.update(stage=name, command=command)
            save(dest / 'receipt.json', receipt)
            print('STAGE', name, str(dest), flush=True)
            with (dest / (name + '.log')).open('xb') as stream:
                process = subprocess.Popen(command, cwd=cwd, shell=False, stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=subprocess.STDOUT)
                code = process.wait()
            text = (dest / (name + '.log')).read_bytes().decode('gb18030', errors='replace')
            if code or re.search(validators.VENDOR_ERROR, text, re.M | re.I):
                raise RuntimeError('Vendor failed: ' + name)
            verify()

        if vendor_help:
            action('vendor_help', 'pnr -help\n', dest / 'help')
            receipt.update(status='help_complete')
            return
        original = analyze(FAILED / 'final_sta/report_timing/top.rtr')
        save(dest / 'original_failure.json', original)
        for tree in ('source', 'ipcore'):
            shutil.copytree(FAILED / 'inputs' / tree, dest / 'inputs' / tree)
        work = dest / 'work'
        work.mkdir()
        for tree in ('synthesize', 'device_map'):
            shutil.copytree(FAILED / 'work' / tree, work / tree)
        prior = dest / 'prior_route'
        shutil.copytree(FAILED / 'work/place_route', prior)
        project = (FAILED / 'work/project.pds').read_bytes().replace(
            (FAILED / 'inputs').as_posix().encode(), (dest / 'inputs').as_posix().encode())
        (work / 'project.pds').write_bytes(project)
        for path in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', project):
            resolved = Path(path.decode('ascii')).resolve()
            if not resolved.is_file() or (dest / 'inputs') not in resolved.parents:
                raise RuntimeError('Project input not private: ' + str(resolved))
        mapped = work / 'device_map/top_map.adf'
        pcf = work / 'device_map/top.pcf'
        synthesis = work / 'synthesize/top_syn.adf'
        identities = {str(p): sha(p) for p in (mapped, pcf, synthesis)}
        save(dest / 'reused_map_provenance.json', identities)
        # Lift the abort limit only; retain every inherited PNR option. Do not use
        # input_place_db_file: the first isolated trial produced incorrect IO-bank
        # metadata (every pin BANKL6), and the strict pin gate rejected that route.
        # Reuse the exact map and physical constraints; run ordinary PNR.
        body = (FAILED / 'strong_pnr.tcl').read_bytes().decode('ascii')
        body = body.replace((FAILED / 'work').as_posix(), work.as_posix())
        body = body.replace(ARCH.strip(), '').strip()
        if body.count('-max_hold_violated_paths_num 15000') != 1:
            raise RuntimeError('Unexpected inherited PNR options')
        body = body.replace('-max_hold_violated_paths_num 15000', '-max_hold_violated_paths_num 50000')
        body += '\n'
        action('reroute', body, work)
        route = work / 'place_route/top_pnr.adf'
        route_hash = sha(route)
        if any(sha(Path(p)) != digest for p, digest in identities.items()):
            raise RuntimeError('Reused synthesis/map/physical constraints changed')
        pin = work / 'place_route/top_prr.prt'
        receipt.update(stage='pin_verification')
        save(dest / 'receipt.json', receipt)
        actual = validators.pinmap(pin)
        if actual != validators.pinmap(FROZEN / 'routed/top_prr.prt'):
            raise RuntimeError('Pin equality failed')
        save(dest / 'pin_audit.json', dict(identical=True, ports=len(actual), report_sha256=sha(pin)))
        action('routed_phy', '.switch_db -input {' + route.as_posix() + '} -output {' +
               (dest / 'routed_phy.txt').as_posix() + '}\n', dest / 'routed_phy')
        physical = validators.phy(dest / 'routed_phy.txt')
        if physical != validators.phy(FROZEN / 'routed_phy.txt'):
            raise RuntimeError('HSST sites/dedicated connections changed')
        save(dest / 'phy_audit.json', dict(identical=True, actual=physical, route_sha256=route_hash))
        # Attribute the exact reused candidate synthesis, not the baseline RAM review.
        resource = work / 'synthesize/apm_drm_lutram_utilization.log'
        raw = resource.read_bytes()
        histories = []
        routed_text = (dest / 'routed_phy.txt').read_bytes()
        for prefix in ('ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top'):
            instance = prefix.encode() + b'/u_motion_tap/u_detector/history'
            start = raw.find(instance)
            if start < 0:
                raise RuntimeError('Motion history missing: ' + prefix)
            block = raw[start:]
            end = block.find(b'|---')
            block = block[:end]
            names = re.findall(rb'history_([0-7])\s*\|\s*32 K x 1\s*\|\s*READ_BEFORE_WRITE\s*\|\s*/\s*\|\s*SINGLE_PORT\s*\|\s*GTP_DRM36K_E1', block)
            if sorted(names) != [str(i).encode() for i in range(8)]:
                raise RuntimeError('Motion BRAM/read-first attribution failed: ' + prefix)
            # Routed annotation must retain each attributable physical memory.
            banks = []
            for i in range(8):
                bank = instance + b'_' + str(i).encode() + b'/gopdrm_36k'
                annotation = re.search(rb'\(INSTANNOTATE\s+\(INSTREF\s+\\?' + re.escape(bank) +
                    rb'\s*\)\s*\(PLACE\s+impl_drm\s+\(DEVINSTREF\s+DRM\s+\(SITEREF\s+(\d+)\s+(\d+)', routed_text)
                if not annotation:
                    raise RuntimeError('Motion history absent from routed DB: ' + prefix + '/' + str(i))
                banks.append(dict(instance=bank.decode(), site=[int(x) for x in annotation.groups()]))
            histories.append(dict(instance=instance.decode(), physical_banks=8,
                                  physical_bank_depth=32768, width=8, mode='read_first',
                                  routed_banks=banks,
                                  evidence=block.decode('ascii', errors='replace')))
        del routed_text
        save(dest / 'motion_resource_proof.json', dict(histories=histories, evidence_sha256=sha(resource),
             mapped_sha256=sha(mapped), synthesized_sha256=sha(synthesis), route_sha256=route_hash,
             note='Physical 32K banks implement the unchanged logical 19200-byte history; RTL and map reused exactly.'))
        action('full_sta', 'report_timing -input_db_file {' + route.as_posix() +
               '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n', dest / 'final_sta')
        report = dest / 'final_sta/report_timing/top.rtr'
        save(dest / 'final_sta_analysis.json', analyze(report))
        rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')
        if sha(route) != route_hash:
            raise RuntimeError('Audited route changed')
        report_hash = sha(report)
        receipt.update(pin_equivalence='PASS', phy_equivalence='PASS', motion_resources='PASS',
                       route_sha256=route_hash, report_sha256=report_hash, timing_rows=rows)
        save(dest / 'final_sta_proof.json', receipt)
        # Final production multi-corner min/max audit is the hard bitgen gate.
        action('bitgen', 'gen_bit_stream -input_db_file {' + route.as_posix() +
               '} -force_to_run -create_bit_file TRUE\n', dest / 'bitgen')
        bits = list((dest / 'bitgen').rglob('*.sbit'))
        if len(bits) != 1 or not bits[0].stat().st_size or sha(route) != route_hash or sha(report) != report_hash:
            raise RuntimeError('Bitgen provenance failed')
        shutil.copy2(bits[0], dest / 'top.sbit')
        verify()
        receipt.update(status='built_for_parent_review', bit_sha256=sha(dest / 'top.sbit'),
                       finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        print('BUILD_ARTIFACT', dest / 'top.sbit', flush=True)
    except Exception as error:
        if dest:
            receipt.update(status='blocked', blocker=str(error), error_stage=receipt.get('stage'),
                           finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        raise
    finally:
        if dest:
            save(dest / 'receipt.json', receipt)
            print('RECOVERY_RECEIPT', dest / 'receipt.json', flush=True)
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--run', action='store_true')
    modes.add_argument('--vendor-help', action='store_true')
    args = parser.parse_args()
    preflight()
    if args.check:
        print('PASS completed parent / frozen hashes / candidate inputs / idle vendor')
    else:
        run(args.vendor_help)
