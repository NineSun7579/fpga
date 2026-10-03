"""Production 50K flow. Launch through build_50k_final.ps1 for a visible live tee.

--prepare validates/snapshots only. --run executes the prepared immutable inputs.
Every vendor action is sequential; bitgen accepts only the STA-proven audited ADF.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from audit_50k_physical import audit_pcf, audit_dump

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1] / 'ov5640_sfp480p_test/ov5640_sfp480p_test'
BIN = Path('C:/pango/PDS_2022.2-SP6.4/bin')
PDS = BIN / 'pds_shell.exe'
DESIGN = 'hdmi_ddr_ov5640_top'
ARCH = 'set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484\n'
CLOCKS = ('sys_clk', 'cfg_clk', 'clk_25M', 'cam1_sccb', 'cam2_sccb',
          'cmos1_pclk', 'cmos2_pclk', 'cmos1_pclk_16bit', 'cmos2_pclk_16bit',
          'p_clk2core_tx_2', 'mrg_clk')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(p, data):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf8')
    tmp.replace(p)


def idle():
    query = "Get-Process | Where-Object { $_.ProcessName -match '^(pds|pds_shell|pnr|ta|bitgen)$' } | Select-Object Id,ProcessName | ConvertTo-Json -Compress"
    busy = subprocess.check_output(['powershell', '-NoProfile', '-Command', query], text=True).strip()
    if busy:
        raise RuntimeError('Vendor runtime already active: ' + busy)


def inputs():
    paths = list((ROOT / 'source').rglob('*')) + list(ROOT.glob('*.fdc'))
    paths = [p for p in paths if p.is_file()]
    if len(paths) != 293:
        raise RuntimeError(f'Expected 293 source/constraint files, got {len(paths)}')
    paths += [ROOT / 'build.pds']
    paths += [p for p in (ROOT / 'ipcore').rglob('*') if p.is_file()]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def check_inputs(dest):
    original = json.loads((dest / 'input_sha256.json').read_text())
    current = inputs()
    changed = [n for n in sorted(original.keys() | current.keys()) if original.get(n) != current.get(n)]
    save(dest / 'source_audit_latest.json', {'checked': len(original), 'changed_or_missing': changed})
    if changed:
        raise RuntimeError('Production inputs changed: ' + repr(changed))


def project_configuration(content):
    """Compare S-expressions while discarding only vendor runtime metadata."""
    tokens = re.findall(rb'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', content)
    ignored = {b'_comment', b'_timespec', b'_gci_state', b'_db_output', b'_output'}
    position = 0
    def parse():
        nonlocal position
        token = tokens[position]
        position += 1
        if token != b'(':
            return token
        values = []
        while tokens[position] != b')':
            value = parse()
            if value is not None:
                values.append(value)
        position += 1
        return None if values and values[0] in ignored else values
    result = parse()
    if position != len(tokens):
        raise RuntimeError('Unexpected project syntax')
    return result


def script(dest, name, text):
    p = dest / (name + '.tcl')
    p.write_text(text, encoding='ascii')
    return p


def execute(dest, name, command, cwd=ROOT, data=None, timeout=5400):
    idle()
    check_inputs(dest)
    print('STAGE ' + name + ': ' + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    save(dest / 'status.json', {'status': 'running', 'stage': name, 'runner_pid': os.getpid(), 'artifact_dir': str(dest)})
    log = dest / (name + '.log')
    with log.open('wb') as stream:
        p = subprocess.Popen([str(x) for x in command], cwd=cwd, stdin=subprocess.PIPE if data else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        save(dest / 'active_process.json', {'stage': name, 'pid': p.pid, 'command': [str(x) for x in command]})
        def expire():
            subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], capture_output=True)
        timer = threading.Timer(timeout, expire)
        timer.start()
        try:
            if data:
                p.stdin.write(data)
                p.stdin.close()
            for line in iter(p.stdout.readline, b''):
                stream.write(line)
                stream.flush()
                print(line.decode('gb18030', errors='replace').rstrip(), flush=True)
            code = p.wait()
        finally:
            timer.cancel()
    text = log.read_bytes().decode('gb18030', errors='replace')
    if code or re.search(r'^E:|invalid command name|Public-4023', text, re.M):
        raise RuntimeError(f'{name} failed (exit {code}); inspect {log}')
    check_inputs(dest)
    return text


def action(dest, name, tcl, work=ROOT):
    work.mkdir(parents=True, exist_ok=True)
    return execute(dest, name, [PDS, '-file', tcl, '-work_dir', work, '-project_name', name], cwd=work)


def prepare():
    idle()
    manifest = inputs()
    pds = (ROOT / 'build.pds').read_bytes()
    fdc = (ROOT / 'ov5640_sfp480p_test.fdc').read_bytes()
    if b'(_device PGL50H)' not in pds or b'define_attribute {n:mrg_clk} {PAP_CLOCK_ASSIGN} {GTP_CLKBUFG}' not in fdc:
        raise RuntimeError('Wrong device or missing merge global-clock constraint')
    dest = ROOT / time.strftime('bitstream_final_50k_%Y%m%d_%H%M%S')
    dest.mkdir()
    save(dest / 'input_sha256.json', manifest)
    source = {n: h for n, h in manifest.items() if n.startswith('source/') or n.endswith('.fdc')}
    save(dest / 'source_sha256.json', source)
    with zipfile.ZipFile(dest / 'sources.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for n in source:
            archive.write(ROOT / n, n)
    shutil.copy2(ROOT / 'build.pds', dest / 'build.pds')
    for name in ('build_50k_final.py', 'build_50k_final.ps1', 'audit_50k_physical.py', 'audit_sta50k_mapped_constraints.py',
                 'apply_sta50k_postmap_interactive.py', 'sta50k_mapped_enumerate.tcl', 'sta50k_holdexperiment.tcl'):
        shutil.copy2(TOOLS / name, dest / name)
    package_report = ROOT / 'bitstream_final_50k_20261002_222104/original_full_route' / (DESIGN + '_prr.prt')
    shutil.copy2(package_report, dest / 'package_pin_site_reference.prt')
    save(dest / 'package_reference.json', {'source': str(package_report), 'sha256': sha(package_report),
         'purpose': 'Vendor package site-to-ball/bank mapping only; old design assignments are invalid'})
    helptext = execute(dest, 'vendor_help', [PDS], data=b'help dev_map\nhelp pnr\nhelp gen_bit_stream\nhelp report_timing\nexit\n', timeout=60)
    for token in ('dev_map :', 'gen_bit_stream :', '-input_db_file', '-fix_hold_violation_in_route'):
        if token not in helptext:
            raise RuntimeError('Vendor help missing required capability: ' + token)
    base = (TOOLS / 'sta50k_holdexperiment.tcl').read_text(encoding='ascii').splitlines()[-1]
    script(dest, 'production_pnr', ARCH + 'add_constraint -physical -pcf {' + (ROOT / ('device_map/' + DESIGN + '.pcf')).as_posix() + '}\nset mapped {' + (ROOT / ('device_map/' + DESIGN + '_map.adf')).as_posix() + '}\n' + base + '\n')
    check_inputs(dest)
    save(dest / 'status.json', {'status': 'prepared', 'artifact_dir': str(dest), 'source_count': len(source)})
    print('ARTIFACT_DIRECTORY: ' + str(dest), flush=True)
    return dest


def prove_report(dest, report, route):
    text = report.read_bytes().decode('gb18030', errors='replace')
    problems = []
    if 'Timing Models: Production' not in text or 'Timing analysis mode : multi corner' not in text:
        problems.append('Missing production models or multi-corner timing')
    if 'Design Summary : All Constraints Met.' not in text or 'Slack (VIOLATED)' in text:
        problems.append('STA reports violated constraints')
    rows = []
    for kind in ('Setup', 'Hold', 'Recovery', 'Removal'):
        for corner in ('Slow', 'Fast'):
            match = re.search(kind + r' Summary\(' + corner + r' Corner\):(.*?)(?=\n=+)', text, re.S)
            if not match:
                problems.append(f'Missing {kind} {corner} summary')
                continue
            found = re.findall(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', match[1], re.M)
            rows += [{'kind': kind, 'corner': corner, 'launch': a, 'capture': b, 'slack': float(s), 'failing': int(f), 'total': int(t)} for a,b,s,_,f,t in found]
            if any(float(s) < 0 or int(f) != 0 for _,_,s,_,f,_ in found):
                problems.append(f'Negative slack/failing endpoints in {kind} {corner}')
            if kind in ('Setup', 'Hold'):
                for clock in CLOCKS:
                    if not any(a == clock and b == clock and int(t) > 0 for a,b,_,_,_,t in found):
                        problems.append(f'Missing local {kind} {corner} clock coverage: {clock}')
                related = [('cmos1_pclk','cmos1_pclk_16bit'), ('cmos2_pclk','cmos2_pclk_16bit')]
                # Audited Gray max-delay -datapath_only deliberately replaces
                # cross-clock hold checks; local hold checks remain mandatory.
                if kind == 'Setup':
                    related += [('mrg_clk','p_clk2core_tx_2'), ('p_clk2core_tx_2','mrg_clk')]
                for a,b in related:
                    if not any(x == a and y == b and int(t) > 0 for x,y,_,_,_,t in found):
                        problems.append(f'Missing related paths {kind} {corner}: {a}->{b}')
    # The two CDC directions must retain exactly ten constrained Gray destinations.
    for a,b in (('mrg_clk','p_clk2core_tx_2'), ('p_clk2core_tx_2','mrg_clk')):
        for corner in ('Slow','Fast'):
            if not any(r['kind'] == 'Setup' and r['corner'] == corner and r['launch'] == a and r['capture'] == b and r['total'] == 10 for r in rows):
                problems.append(f'Gray destination coverage is not ten: {a}->{b} {corner}')
    proof = {'report': str(report), 'report_sha256': sha(report), 'audited_route_sha256': sha(route), 'summary_rows': rows, 'problems': problems}
    save(dest / 'final_sta_proof.json', proof)
    if problems:
        raise RuntimeError('Final STA blocked: ' + '; '.join(problems))


def run(dest, resume_compiled=False, resume_routed=False, resume_sta=False):
    idle()
    if resume_sta:
        check_inputs(dest)
        audited = dest / 'audited_route' / (DESIGN + '_pnr.adf')
        report = dest / 'final_sta/report_timing' / (DESIGN + '.rtr')
        prior = json.loads((dest / 'final_sta_proof.json').read_text())
        if sha(audited) != prior['audited_route_sha256'] or sha(report) != prior['report_sha256']:
            raise RuntimeError('STA report or audited route changed before resume')
        prove_report(dest, report, audited)
        return finish_verified_sta(dest, audited, report)
    if resume_routed:
        check_inputs(dest)
        route = ROOT / ('place_route/' + DESIGN + '_pnr.adf')
        protected = dest / 'original_full_route' / route.name
        if not protected.is_file() or sha(route) != sha(protected):
            raise RuntimeError('Resume route does not match preserved full-route copy')
        return finish_route(dest)
    if not resume_compiled and json.loads((dest / 'status.json').read_text())['status'] != 'prepared':
        raise RuntimeError('Runner requires a new prepared archive; no destructive resume')
    # PDS rewrites project timestamps/action status. Run a sibling project with
    # identical source registration so the original build.pds stays immutable.
    flow_project = ROOT / (dest.name + '_flow.pds')
    if flow_project.exists():
        raise RuntimeError('Private flow project already exists')
    if resume_compiled:
        original = (dest / 'build.pds').read_bytes()
        current = (ROOT / 'build.pds').read_bytes()
        expected = json.loads((dest / 'input_sha256.json').read_text())
        actual = inputs()
        if any(expected.get(n) != actual.get(n) for n in expected.keys() | actual.keys() if n != 'build.pds'):
            raise RuntimeError('Protected source/IP/constraint changed before recovery')
        if project_configuration(original) != project_configuration(current):
            raise RuntimeError('PDS changed build configuration; refusing recovery')
        compiled_log = (dest / 'compile.log').read_bytes()
        compiled = ROOT / ('compile/' + DESIGN + '_comp.adf')
        if b'Process "Compile" done.' not in compiled_log or not compiled.is_file():
            raise RuntimeError('No verified compile to resume')
        (dest / 'vendor_compiled_build.pds').write_bytes(current)
        flow_project.write_bytes(current)
        (ROOT / 'build.pds').write_bytes(original)
        save(dest / 'project_metadata_recovery.json', {'configuration_unchanged': True, 'original_project_restored': True,
              'private_flow_project': str(flow_project), 'compiled_sha256': sha(compiled)})
    else:
        shutil.copy2(ROOT / 'build.pds', flow_project)
    check_inputs(dest)
    if not resume_compiled:
        for name in ('compile', 'synthesize', 'device_map', 'place_route', 'report_timing', 'generate_bitstream', 'generate_netlist'):
            p = ROOT / name
            if p.exists():
                shutil.move(str(p), str(dest / ('previous_' + name)))
    for stage in (('synthesize', 'dev_map') if resume_compiled else ('compile', 'synthesize', 'dev_map')):
        execute(dest, stage, [PDS, '-project', flow_project, '-run', stage, '-work_dir', ROOT])
        if project_configuration((dest / 'build.pds').read_bytes()) != project_configuration(flow_project.read_bytes()):
            raise RuntimeError('Private flow project build configuration changed')
        shutil.copy2(flow_project, dest / ('flow_project_after_' + stage + '.pds'))
    mapped = ROOT / ('device_map/' + DESIGN + '_map.adf')
    if not mapped.is_file():
        raise RuntimeError('Fresh mapped database missing')
    save(dest / 'mapped_sha256.json', {'db': str(mapped), 'sha256': sha(mapped)})
    pcf = ROOT / ('device_map/' + DESIGN + '.pcf')
    save(dest / 'physical_pcf_audit.json', audit_pcf(ROOT / 'ov5640_sfp480p_test.fdc', pcf))
    shutil.copy2(pcf, dest / 'production_physical.pcf')
    shutil.copy2(mapped, dest / mapped.name)
    pnrlog = action(dest, 'physical_pnr', dest / 'production_pnr.tcl')
    route = ROOT / ('place_route/' + DESIGN + '_pnr.adf')
    if not route.is_file():
        raise RuntimeError('Fresh routed database missing')
    shutil.copytree(ROOT / 'place_route', dest / 'original_full_route')
    return finish_route(dest)


def finish_route(dest):
    route = ROOT / ('place_route/' + DESIGN + '_pnr.adf')
    protected = dest / 'original_full_route' / route.name
    route_hash = sha(route)
    prove_physical(dest, route, 'original')
    clock_report = ROOT / 'place_route/clock_utilization.txt'
    clocktext = clock_report.read_bytes().decode('gb18030', errors='replace')
    pnrlog = (dest / 'physical_pnr.log').read_bytes().decode('gb18030', errors='replace')
    save(dest / 'merge_clock_architecture.json', {'buffer_placement_lines': [x for x in clocktext.splitlines() if 'mrg_clk/' in x and 'USCM_' in x],
        'source_to_buffer_srb': 'clock path from mrg_clk/opit_0_inv:Q to clkbufg_0/gopclkbufg:CLK is routed by SRB' in pnrlog,
        'note': 'Fabric divider source reaches global buffer via SRB; buffer output drives the global clock loads. Final multi-corner STA must prove timing.'})
    if not re.search(r'^\|\s*mrg_clk/.*\|.*clkbufg.*USCM_', clocktext, re.M):
        raise RuntimeError('Merge clock lacks verified global-buffer placement')
    enumout = dest / 'enumeration_output'
    enumout.mkdir(exist_ok=True)
    execute(dest, 'enumerate_route', [BIN / 'ta.exe', route, '-rtr', enumout, '-tcl', dest / 'sta50k_mapped_enumerate.tcl'], timeout=300)
    if sha(route) != route_hash:
        raise RuntimeError('Enumeration changed original route')
    fdc = dest / 'audited_postroute.fdc'
    execute(dest, 'audit_objects', [sys.executable, dest / 'audit_sta50k_mapped_constraints.py', '--log', dest / 'enumerate_route.log', '--db', route, '--expected-db-sha256', route_hash, '--output', fdc], timeout=60)
    audited = dest / 'audited_route' / route.name
    if audited.parent.exists():
        # Preserve interrupted/failed installs; installation always uses a new DB.
        saved = dest / time.strftime('interrupted_install_%Y%m%d_%H%M%S')
        shutil.move(str(audited.parent), str(saved))
    execute(dest, 'install_audited_constraints', [sys.executable, dest / 'apply_sta50k_postmap_interactive.py', '--db', route, '--fdc', fdc, '--audit', fdc.with_suffix('.fdc.audit.json'), '--output-db', audited], timeout=960)
    prove_physical(dest, audited, 'audited')
    prove_physical_preserved(dest)
    fullwork = dest / 'final_sta'
    sta = script(dest, 'final_sta', ARCH + 'report_timing -input_db_file {' + audited.as_posix() + '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n')
    audited_hash = sha(audited)
    action(dest, 'final_sta', sta, fullwork)
    report = fullwork / ('report_timing/' + DESIGN + '.rtr')
    prove_report(dest, report, audited)
    return finish_verified_sta(dest, audited, report)


def finish_verified_sta(dest, audited, report):
    route = ROOT / ('place_route/' + DESIGN + '_pnr.adf')
    protected = dest / 'original_full_route' / route.name
    route_hash = json.loads((dest / 'audited_postroute.fdc.audit.json').read_text())['db_sha256']
    audited_hash = sha(audited)
    if sha(route) != route_hash or sha(protected) != route_hash:
        raise RuntimeError('Original route no longer matches external object audit')
    dumpwork = dest / 'constraint_proof'
    dumpwork.mkdir(exist_ok=True)
    # export_fdc is project/DevMap-only and .switch_db omits SDC. Prove native
    # enforcement by comparing fresh production reports on the two exact DBs.
    baseline_work = dumpwork / 'original_sta'
    baseline_tcl = script(dest, 'original_sta', ARCH + 'report_timing -input_db_file {' + protected.as_posix() + '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n')
    baseline_report = baseline_work / ('report_timing/' + DESIGN + '.rtr')
    if not baseline_report.is_file():
        action(dest, 'original_sta', baseline_tcl, baseline_work)
    prove_constraints_from_reports(dest, baseline_report, report)
    if sha(audited) != audited_hash or sha(route) != route_hash or sha(protected) != route_hash:
        raise RuntimeError('Protected or audited routed database changed during STA')
    check_inputs(dest)
    prove_physical(dest, protected, 'original')
    prove_physical(dest, audited, 'audited')
    physical = prove_physical_preserved(dest)
    bitwork = dest / 'final_bitgen'
    bit = script(dest, 'final_bitgen', ARCH + 'gen_bit_stream -input_db_file {' + audited.as_posix() + '} -force_to_run -create_bit_file TRUE\n')
    action(dest, 'final_bitgen', bit, bitwork)
    if sha(audited) != audited_hash or sha(route) != route_hash:
        raise RuntimeError('Bitgen changed routed input')
    bits = list(bitwork.rglob('*.sbit'))
    if len(bits) != 1:
        raise RuntimeError('Expected exactly one fresh generated .sbit, got ' + repr(bits))
    shutil.copy2(bits[0], dest / bits[0].name)
    check_inputs(dest)
    save(dest / 'status.json', {'status': 'complete', 'artifact_dir': str(dest), 'bitstream': str(dest / bits[0].name),
                              'bit_sha256': sha(bits[0]), 'audited_route_sha256': audited_hash, 'original_route_sha256': route_hash,
                               'report_sha256': sha(report), 'source_inputs_unchanged': True})
    final_status = json.loads((dest / 'status.json').read_text())
    final_status.update({'physical_audit_passed': True, 'physical_io_sha256': physical['physical_io_sha256'],
                         'placements_sha256': physical['placements_sha256']})
    save(dest / 'status.json', final_status)
    print('COMPLETE: ' + str(dest / bits[0].name), flush=True)


def prove_physical(dest, db, label):
    proof_file = dest / ('physical_' + label + '_proof.json')
    db_hash = sha(db)
    if proof_file.is_file():
        proof = json.loads(proof_file.read_text())
        if proof.get('db_sha256') == db_hash and not proof['problems']:
            return proof
    work = dest / ('physical_' + label + '_extract_' + time.strftime('%Y%m%d_%H%M%S'))
    work.mkdir()
    copy = work / db.name
    shutil.copy2(db, copy)
    dump = work / 'actual_database.txt'
    commands = ARCH + 'mpnr -input {' + copy.as_posix() + '}\n.switch_db -input {' + copy.as_posix() + '} -output {' + dump.as_posix() + '}\nexit\n'
    execute(dest, 'physical_' + label + '_extract', [PDS], cwd=work, data=commands.encode('ascii'), timeout=300)
    if sha(db) != db_hash or sha(copy) != db_hash:
        raise RuntimeError('Physical extraction modified the routed database')
    reference = dest / 'package_pin_site_reference.prt'
    if sha(reference) != json.loads((dest / 'package_reference.json').read_text())['sha256']:
        raise RuntimeError('Package site reference changed')
    proof = audit_dump(ROOT / 'ov5640_sfp480p_test.fdc', dump, reference)
    proof.update({'db_sha256': db_hash, 'db': str(db), 'extracted_from_exact_copy': True})
    save(proof_file, proof)
    if proof['problems']:
        raise RuntimeError('Physical bitstream gate blocked: ' + '; '.join(proof['problems']))
    print(f'PHYSICAL_PROOF {label}: all 40 implemented IOs, 2 dangling keys, 10 dedicated HSST pads; {proof["placement_count"]} placements audited', flush=True)
    return proof


def prove_physical_preserved(dest):
    before = json.loads((dest / 'physical_original_proof.json').read_text())
    after = json.loads((dest / 'physical_audited_proof.json').read_text())
    for key in ('physical_io_sha256', 'placements_sha256', 'placement_count'):
        if before[key] != after[key]:
            raise RuntimeError('Timing-only install changed physical implementation: ' + key)
    save(dest / 'physical_preserved.json', {'all_placements_identical': True, 'all_io_parameters_identical': True,
         'original_db_sha256': before['db_sha256'], 'audited_db_sha256': after['db_sha256'],
         'physical_io_sha256': after['physical_io_sha256'], 'placements_sha256': after['placements_sha256']})
    return after


def prove_constraints_from_reports(dest, baseline_report, audited_report):
    def text(path):
        return path.read_bytes().decode('gb18030', errors='replace').replace('\r', '')
    baseline, audited = text(baseline_report), text(audited_report)
    problems = []
    sections = {}
    for heading in ('Clock Summary:', 'Clock Groups:'):
        def section(t):
            match = re.search(re.escape(heading) + r'(.*?)(?=\n=+)', t, re.S)
            return re.sub(r'\s+', ' ', match[1]).strip() if match else None
        a,b = section(baseline), section(audited)
        sections[heading] = bool(a and a == b)
        if not sections[heading]:
            problems.append('Original/audited clock definition or group mismatch: ' + heading)
    def paths(t):
        for m in re.finditer(r'^Startpoint\s*:', t, re.M):
            end = t.find('\nStartpoint', m.end())
            yield t[m.start():end if end >= 0 else len(t)]
    def evidence(t):
        uncertainties, gray = {}, {}
        for block in paths(t):
            typ = re.search(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)', block, re.M)
            clocks = re.findall(r'^ Clock (\S+) \(', block, re.M)
            if not typ:
                continue
            if clocks and clocks[0] == clocks[-1]:
                key = '|'.join((clocks[0], typ[1], typ[2]))
                values = re.findall(r'clock uncertainty\s+(-?\d+\.\d+)', block)
                uncertainties.setdefault(key, set()).update(abs(float(x)) for x in values)
            endpoint = re.search(r'^Endpoint\s*:\s*(.*)', block, re.M)
            bound = re.search(r'Timing Exception\s*:\s*MaxDelay Path (\d+\.\d+)ns -datapath_only', block)
            if endpoint and bound and typ[1] == 'max':
                for pin in ('wptr_rd1', 'rptr_wr1'):
                    bit = re.search(re.escape(pin) + r'\[(\d+)\].*/D$', endpoint[1].strip())
                    if bit:
                        key = '|'.join((pin, typ[2], bit[1]))
                        gray[key] = float(bound[1])
        return uncertainties, gray
    old_u, _ = evidence(baseline)
    new_u, gray = evidence(audited)
    uncertainty_evidence = {}
    for clock in CLOCKS:
        for kind in ('max','min'):
            for corner in ('slow','fast'):
                key = '|'.join((clock,kind,corner))
                before,after = old_u.get(key),new_u.get(key)
                uncertainty_evidence[key] = {'original': sorted(before) if before else [], 'audited': sorted(after) if after else []}
                if before != after:
                    problems.append('Clock uncertainty changed: ' + key)
    fdc = (ROOT / 'ov5640_sfp480p_test.fdc').read_bytes()
    required_u = re.findall(rb'^set_clock_uncertainty\s+\{([\d.]+)\}\s+\[get_clocks\s+\{([^}]+)\}\]', fdc, re.M)
    for value,clock_bytes in required_u:
        clock = clock_bytes.decode('ascii')
        for kind in ('max','min'):
            for corner in ('slow','fast'):
                key = '|'.join((clock,kind,corner))
                actual = new_u.get(key)
                # Setup includes the vendor's additional 0.050ns model margin;
                # require unchanged original value and no source-FDC reduction.
                if not actual or min(actual) < float(value) or (kind == 'min' and actual != {float(value)}):
                    problems.append('Required source FDC uncertainty not enforced: ' + key)
    for pin,delay in (('wptr_rd1',16.0),('rptr_wr1',8.0)):
        for corner in ('slow','fast'):
            for bit in range(10):
                key = '|'.join((pin,corner,str(bit)))
                if gray.get(key) != delay:
                    problems.append('Missing exact Gray datapath-only bound: ' + key)
    proof = {'method': 'fresh native production STA on hash-matched original and audited route; compare clock definitions/groups, all local min/max corner uncertainties, and all 40 Gray bound paths',
             'original_report_sha256': sha(baseline_report), 'audited_report_sha256': sha(audited_report),
             'clock_sections_preserved': sections, 'uncertainties': uncertainty_evidence, 'gray_bounds': gray, 'problems': problems}
    save(dest / 'constraints_preserved.json', proof)
    if problems:
        raise RuntimeError('Constraint enforcement/preservation proof blocked: ' + '; '.join(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run', type=Path)
    parser.add_argument('--resume-compiled', action='store_true', help='Recover only verified compile after vendor project metadata rewrite')
    parser.add_argument('--resume-routed', action='store_true', help='Continue only a route matching its preserved full-route copy')
    parser.add_argument('--resume-sta', action='store_true', help='Continue only the exact audited route and completed STA report')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.run:
        dest = args.run.resolve()
        try:
            run(dest, args.resume_compiled, args.resume_routed, args.resume_sta)
        except Exception as error:
            save(dest / 'status.json', {'status': 'blocked', 'blocker': str(error), 'artifact_dir': str(dest)})
            print('BLOCKED: ' + str(error), flush=True)
            raise
    else:
        parser.error('Choose --prepare or --run ARTIFACT_DIRECTORY')


if __name__ == '__main__':
    sys.stdout.reconfigure(errors='backslashreplace')
    main()
