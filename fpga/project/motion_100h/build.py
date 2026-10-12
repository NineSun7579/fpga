"""Sequential isolated 100H flow, physical/STA/resource gates and exact bit provenance."""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from prepare_project import HERE as H, WORK as W, sha, save, prepare, registered, strip_runtime

PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH = 'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
VENDOR_ERROR = r'^E:|invalid command name|Public-4023|no objects matched|empty collection'

def status(stage, **values):
    row = {'stage': stage, 'updated': time.strftime('%Y-%m-%d %H:%M:%S'), **values}
    save(H / 'status.json', row)
    print(json.dumps(row), flush=True)

def idle():
    query = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match "
             "'^(pds|pds_shell|pnr|ta|bitgen|pne|ppc|ppp|cdt_js|cdt_cfg|cdt_cfg_shell)\\.exe$'} "
             '| Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress')
    busy = subprocess.check_output(['powershell', '-NoProfile', '-Command', query], text=True).strip()
    if busy:
        raise RuntimeError('Vendor/JTAG processes active; wait for completion: ' + busy)

def inventory():
    result = {}
    for tree in ('source', 'ipcore'):
        for path in (H / tree).rglob('*'):
            if path.is_file():
                if path.is_symlink() or H not in path.resolve().parents:
                    raise RuntimeError('Linked input: ' + str(path))
                result[path.relative_to(H).as_posix()] = sha(path)
    for path in [H / 'baseline_project.pds', H / 'baseline_manifest.json', W / 'project.pds',
                 H / 'preparation.json', *sorted((H / 'baseline').glob('*'))]:
        if path.is_file():
            result[path.relative_to(H).as_posix()] = sha(path)
    return result

def check_inputs(dest):
    if inventory() != json.loads((dest / 'input_sha256.json').read_text()):
        raise RuntimeError('Protected isolated input changed during build')
    registered((W / 'project.pds').read_bytes())
    if (W / 'flow.pds').exists():
        registered(strip_runtime((W / 'flow.pds').read_bytes()))

def check_archive(dest):
    frozen = json.loads((dest / 'input_sha256.json').read_text())
    for name, digest in frozen.items():
        if name.startswith(('source/', 'ipcore/')):
            if sha(dest / 'inputs' / name) != digest:
                raise RuntimeError('Archived input copy/hash mismatch: ' + name)

def execute(dest, name, args, cwd):
    idle()
    check_inputs(dest)
    status(name, status='running', run=str(dest), command=[str(x) for x in args])
    with (dest / (name + '.log')).open('wb') as stream:
        proc = subprocess.Popen([str(x) for x in args], cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(proc.stdout.readline, b''):
            stream.write(line)
            stream.flush()
            print(line.decode('gb18030', errors='replace').rstrip(), flush=True)
        code = proc.wait()
    text = (dest / (name + '.log')).read_bytes().decode('gb18030', errors='replace')
    if code or re.search(VENDOR_ERROR, text, re.M | re.I):
        raise RuntimeError('Vendor stage failed: ' + name)
    check_inputs(dest)

def action(dest, name, text, work):
    work.mkdir(parents=True, exist_ok=True)
    script = dest / (name + '.tcl')
    script.write_text(ARCH + text, encoding='ascii')
    execute(dest, name, [PDS, '-file', script, '-work_dir', work, '-project_name', name], work)

def pinmap(path):
    rows = {}
    for line in path.read_text(errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            rows[fields[4]] = fields[:4] + fields[5:7]
    if len(rows) < 100:
        raise RuntimeError('Incomplete pin report: ' + str(path))
    return rows

def auditpins(report):
    actual = pinmap(report)
    if actual != pinmap(H / 'baseline/top_prr.prt'):
        raise RuntimeError('Routed pins changed from final 192245 baseline')
    for fdc in (H / 'source/constraints').glob('*.fdc'):
        for line in fdc.read_bytes().decode('ascii', errors='replace').splitlines():
            if line.strip().startswith('#'):
                continue
            match = re.search(r'define_attribute\s+\{p:([^}]+)\}\s+\{(?:PAP_LOC|PAP_IO_LOC)\}\s+\{([^}]+)\}', line)
            if match:
                port, ball = match.groups()
                if port in ('ref_clk_p', 'ref_clk_n'):
                    if ball != {'ref_clk_p': 'F6', 'ref_clk_n': 'E6'}[port]:
                        raise RuntimeError('Dedicated reference pad changed')
                elif port not in actual or actual[port][0] != ball:
                    raise RuntimeError('FDC/routed ball mismatch: ' + port)
    return {'identical': True, 'ports': len(actual), 'report_sha256': sha(report)}

def phy(dump):
    text = dump.read_bytes().decode('gb18030', errors='replace')
    sites = {n: (impl, dev, x, y) for n, impl, dev, x, y in re.findall(
        r'\(INSTANNOTATE \(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(\S+)\s+\(SITEREF\s+(\d+)\s+(\d+)', text)
             if 'HSST' in dev}
    nets = {}
    for name, block in re.findall(r'^          \(NET\s+([^\n]+)\n(.*?)(?=^          \))', text, re.M | re.S):
        name = name.strip()
        match = re.fullmatch(r'\(INDEXED (\S+) (\d+)\)', name)
        if match:
            name = f'{match[1]}[{match[2]}]'
        nets[name.lstrip('\\')] = block
    ports = ['ref_clk_p', 'ref_clk_n'] + [f'{d}{p}[{i}]' for d in ('rx', 'tx')
             for p in ('p', 'n') for i in range(2)] + [f'sfp_l2{d}{p}' for d in ('rx', 'tx') for p in ('p', 'n')]
    connections = {}
    connect_blocks = re.findall(r'^            \(CONNECT[^\n]*\n(.*?)^            \)', text, re.M | re.S)
    for port in ports:
        indexed = re.fullmatch(r'(\w+)\[(\d+)\]', port)
        port_ref = (r'\(INDEXED\s+' + re.escape(indexed[1]) + r'\s+' + indexed[2] + r'\)'
                    if indexed else re.escape(port))
        blocks = [block for block in connect_blocks
                  if re.search(r'\(PORTREF\s+' + port_ref + r'\s*\)', block)]
        pads = [pair for block in blocks for pair in re.findall(
            r'\(PORTREF\s+(PAD(?:_\w+)?|P_(?:RX|TX)_SD[PN])\s+\(INSTREF\s+([^\s()]+)\s*\)', block)]
        if not pads:
            raise RuntimeError('Missing dedicated PHY connection: ' + port)
        connections[port] = sorted(pads)
    if len(sites) < 3:
        raise RuntimeError('Incomplete HSST placement proof')
    return {'hsst_sites': sites, 'dedicated_connections': connections}

def resources(dest):
    # Vendor naming/inference format is not established for this new RAM template.
    # Fail closed: an attributable, hash-bound review is required, not a global RAM count.
    path = dest / 'resource_review.json'
    mapped = W / 'device_map/top_map.adf'
    syn = W / 'synthesize/top_syn.adf'
    proof = {'mapped_sha256': sha(mapped), 'synthesized_sha256': sha(syn),
              'required_histories': 4, 'bits_per_history': 19200 * 8}
    save(dest / 'resource_requirements.json', proof)
    if not path.is_file():
        raise RuntimeError('BRAM attribution/read-first review required: ' + str(path) + '; see BUILD.md and resume this run')
    review = json.loads(path.read_text())
    if any(review.get(key) != value for key, value in proof.items()) or not review.get('reviewer'):
        raise RuntimeError('Resource review does not match exact synthesis/map')
    histories = review.get('histories', [])
    evidence_cache = {}
    expected_instances = {prefix + '/u_motion_tap/u_detector' for prefix in
                          ('ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top')}
    if len(histories) != 4 or {row['instance'] for row in histories} != expected_instances:
        raise RuntimeError('Resource review must attribute exactly CAM1–4 detector histories')
    for row in histories:
        if row.get('depth') != 19200 or row.get('width') != 8 or row.get('mode') != 'read_first':
            raise RuntimeError('History geometry/read-first mode unproven')
        if not row.get('bram_instances') or not row.get('evidence'):
            raise RuntimeError('Missing mapped BRAM instances/evidence')
        for evidence in row['evidence']:
            file = (dest / evidence['file']).resolve()
            if not file.is_file() or not (dest in file.parents or W in file.parents):
                raise RuntimeError('Resource evidence outside current run/work')
            if file not in evidence_cache:
                raw = file.read_bytes()
                import hashlib
                evidence_cache[file] = (hashlib.sha256(raw).hexdigest(),
                                        raw.decode('gb18030', errors='replace'))
            digest, text = evidence_cache[file]
            if digest != evidence['sha256'] or not evidence['quote'] or evidence['quote'] not in text:
                raise RuntimeError('Resource evidence hash/quote mismatch')
    save(dest / 'resource_proof.json', review)

def timing(report, baseline):
    with report.open('rb') as stream:
        text = stream.read(262144).decode('gb18030', errors='replace')
    for token in ('Timing Models: Production', 'Timing analysis mode : multi corner',
                  'Design Summary : All Constraints Met.'):
        if token not in text:
            raise RuntimeError('Full final STA missing: ' + token)
    with report.open('rb') as stream:
        overlap = b''
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            block = overlap + chunk
            if b'Slack (VIOLATED)' in block:
                raise RuntimeError('Final STA has violations')
            overlap = block[-32:]
    expected = set(re.findall(r'^\s*(\w+)\s+\1\s+[-\d.]+', baseline.read_text(), re.M))
    rows = []
    section = None
    for line in text.splitlines():
        match = re.search(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\)', line)
        if match:
            section = tuple(match.groups())
        pulse = re.match(r'^\s*(\w+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', line)
        if pulse and section and section[0] == 'Minimum Pulse Width':
            clock, slack, total, failing, endpoints = pulse.groups()
            if float(slack) < 0 or float(total) < 0 or int(failing):
                raise RuntimeError('Failing pulse-width summary row: ' + line)
            rows.append({'section': section, 'launch': clock, 'capture': clock,
                         'slack': float(slack), 'endpoints': int(endpoints)})
        match = re.match(r'^\s*(\w+)\s+(\w+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', line)
        if match and section:
            launch, capture, slack, total, failing, endpoints = match.groups()
            if float(slack) < 0 or float(total) < 0 or int(failing):
                raise RuntimeError('Failing STA summary row: ' + line)
            rows.append({'section': section, 'launch': launch, 'capture': capture,
                         'slack': float(slack), 'endpoints': int(endpoints)})
    for corner in ('Slow', 'Fast'):
        for kind in ('Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width'):
            group = [r for r in rows if tuple(r['section']) == (kind, corner)]
            if not group:
                raise RuntimeError('Missing nonempty STA section: ' + kind + '/' + corner)
            if kind in ('Setup', 'Hold') and not expected <= {r['capture'] for r in group}:
                raise RuntimeError('Baseline clocks missing from ' + kind + '/' + corner)
    return rows

def run_inner(resume=None):
    idle()
    prepare(check=True)
    reuse_route = False
    if resume:
        dest = Path(resume).resolve()
        if dest.parent != H or not dest.name.startswith('run_'):
            raise RuntimeError('Resume must name a run directory inside this stage')
        check_inputs(dest)
        checkpoint = json.loads((dest / 'mapped_provenance.json').read_text())
        for name, path in [('mapped_sha256', W / 'device_map/top_map.adf'),
                           ('synthesized_sha256', W / 'synthesize/top_syn.adf'),
                           ('pcf_sha256', W / 'device_map/top.pcf')]:
            if checkpoint[name] != sha(path):
                raise RuntimeError('Resume synthesis/map artifact changed')
        if (W / 'place_route').exists():
            prior = json.loads((H / 'status.json').read_text())
            if (prior.get('failed_stage') != 'routed_phy' or prior.get('run') != str(dest)
                    or sha(W / 'place_route/top_pnr.adf') != sha(dest / 'routed/top_pnr.adf')):
                raise RuntimeError('Existing route is not the archived route from the PHY audit failure')
            for name, db in [('baseline_phy', H / 'baseline/top_pnr.adf'),
                             ('routed_phy', W / 'place_route/top_pnr.adf')]:
                if db.as_posix() not in (dest / (name + '.tcl')).read_text():
                    raise RuntimeError('PHY export input does not match checkpoint')
                if not (dest / (name + '.txt')).is_file():
                    raise RuntimeError('Missing completed PHY export')
            reuse_route = True
    else:
        if any((W / name).exists() for name in ('compile', 'synthesize', 'device_map', 'place_route')):
            raise RuntimeError('Fresh work required; preserve old work rather than overwrite it')
        if (W / 'flow.pds').exists() and sha(W / 'flow.pds') != sha(W / 'project.pds'):
            raise RuntimeError('Mutable flow has changed; preserve old work before a fresh build')
        dest = H / ('run_' + time.strftime('%Y%m%d_%H%M%S'))
        dest.mkdir()
        save(dest / 'input_sha256.json', inventory())
        for tree in ('source', 'ipcore'):
            shutil.copytree(H / tree, dest / 'inputs' / tree)
        shutil.copy2(W / 'project.pds', dest / 'project.pds')
        check_inputs(dest)
        check_archive(dest)
        shutil.copy2(W / 'project.pds', W / 'flow.pds')
        for stage in ('compile', 'synthesize', 'dev_map'):
            execute(dest, stage, [PDS, '-project', W / 'flow.pds', '-run', stage, '-work_dir', W], W)
        save(dest / 'mapped_provenance.json', {'mapped_sha256': sha(W / 'device_map/top_map.adf'),
             'synthesized_sha256': sha(W / 'synthesize/top_syn.adf'), 'pcf_sha256': sha(W / 'device_map/top.pcf')})
    check_archive(dest)
    resources(dest)
    pcf, mapped = W / 'device_map/top.pcf', W / 'device_map/top_map.adf'
    script = 'add_constraint -physical -pcf {' + pcf.as_posix() + '}\nset mapped {' + mapped.as_posix() + '}\n'
    script += ('pnr -input_db_file $mapped -force_to_run '
               '-slack_prior_in_global_router TRUE -logic_optimize_enable TRUE '
               '-optimize_multi_corner_timing '
               '-fix_hold_violation -fix_hold_violation_iterations 500 -fix_hold_violation_threshold 100 '
               '-fix_hold_violation_in_route TRUE -fix_hold_violation_threshold_for_clock_path_cross_srb 200 '
               '-fix_hold_violation_threshold_for_clk_tree 200 -max_hold_violated_paths_num 15000 -fast_router FALSE\n')
    if not reuse_route:
        action(dest, 'strong_pnr', script, W)
    route = W / 'place_route/top_pnr.adf'
    route_hash = sha(route)
    if not reuse_route:
        shutil.copytree(W / 'place_route', dest / 'routed')
    save(dest / 'pin_audit.json', auditpins(W / 'place_route/top_prr.prt'))
    for name, db in [('baseline_phy', H / 'baseline/top_pnr.adf'), ('routed_phy', route)]:
        if not reuse_route:
            action(dest, name, '.switch_db -input {' + db.as_posix() + '} -output {' +
                   (dest / (name + '.txt')).as_posix() + '}\n', dest / name)
    reference, actual = phy(dest / 'baseline_phy.txt'), phy(dest / 'routed_phy.txt')
    if reference != actual:
        raise RuntimeError('Actual HSST placements/dedicated pads changed')
    save(dest / 'phy_audit.json', {'identical': True, 'actual': actual, 'route_sha256': route_hash})
    action(dest, 'full_sta', 'report_timing -input_db_file {' + route.as_posix() +
           '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n', dest / 'final_sta')
    report = dest / 'final_sta/report_timing/top.rtr'
    rows = timing(report, H / 'baseline/top_timing_summary_after_hold_fix.txt')
    if sha(route) != route_hash:
        raise RuntimeError('STA/physical audit changed exact routed DB')
    report_hash = sha(report)
    save(dest / 'final_sta_proof.json', {'route_sha256': route_hash, 'report_sha256': report_hash, 'rows': rows})
    # No bitgen until all resource/physical/final multi-corner timing gates pass.
    action(dest, 'bitgen', 'gen_bit_stream -input_db_file {' + route.as_posix() +
           '} -force_to_run -create_bit_file TRUE\n', dest / 'bitgen')
    bits = list((dest / 'bitgen').rglob('*.sbit'))
    if len(bits) != 1 or sha(route) != route_hash or sha(report) != report_hash or not bits[0].stat().st_size:
        raise RuntimeError('Bitgen provenance mismatch')
    shutil.copy2(bits[0], dest / 'top.sbit')
    check_inputs(dest)
    check_archive(dest)
    save(dest / 'bit_provenance.json', {
        'route_sha256': route_hash, 'report_sha256': report_hash,
        'mapped_sha256': sha(mapped), 'pcf_sha256': sha(pcf),
        'resource_proof_sha256': sha(dest / 'resource_proof.json'),
        'pin_proof_sha256': sha(dest / 'pin_audit.json'),
        'phy_proof_sha256': sha(dest / 'phy_audit.json'),
        'input_manifest_sha256': sha(dest / 'input_sha256.json'),
        'bit_sha256': sha(dest / 'top.sbit')})
    status('complete', status='complete', run=str(dest), bit=str(dest / 'top.sbit'),
           bit_sha256=sha(dest / 'top.sbit'), route_sha256=route_hash, report_sha256=sha(report))
    print('BUILD_ARTIFACT: ' + str(dest / 'top.sbit'), flush=True)

def run(resume=None):
    lock = H / 'build.lock'
    # Exclusive stage ownership closes the race between two launchers' idle checks.
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        run_inner(resume)
    finally:
        lock.unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--run', action='store_true')
    parser.add_argument('--resume')
    args = parser.parse_args()
    try:
        if args.check:
            prepare(check=True)
            idle()
            print('PASS readiness; no vendor launch')
        else:
            run(args.resume)
    except Exception as error:
        if args.run:
            previous = json.loads((H / 'status.json').read_text()) if (H / 'status.json').exists() else {}
            status('blocked', status='blocked', blocker=str(error), run=previous.get('run'),
                   failed_stage=previous.get('stage'))
        raise
