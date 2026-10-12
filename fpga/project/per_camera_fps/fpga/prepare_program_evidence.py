"""Assemble verified recovery artifacts; only invoke the programmer with --check.

Never builds, connects to hardware, programs SRAM/Flash, or records acceptance.
All writes are confined to a new deploy_evidence_* directory beside this script.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from build_later import inherited
from prepare import HERE, ROOT, FROZEN, check
from timing_recovery import sha, analyze


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load(path):
    return json.loads(path.read_bytes())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def assemble(source):
    candidate = check()  # Byte-level candidate identity and frozen-source checks.
    validators = inherited()  # Read-only imports; no build/status/vendor calls.
    receipt = load(source / 'receipt.json')
    require(receipt.get('status') == 'built_for_parent_review', 'Recovery incomplete')
    require(receipt['candidate'] == candidate, 'Recovery candidate differs from current candidate')
    parent = Path(receipt['parent']).resolve(strict=True)
    frozen_inputs = load(parent / 'input_sha256.json')
    require({p.relative_to(source / 'inputs').as_posix() for p in
             (source / 'inputs').rglob('*') if p.is_file()} == set(frozen_inputs),
            'Recovery input inventory differs')
    for name, digest in frozen_inputs.items():
        require(sha(source / 'inputs' / name) == digest, 'Input changed: ' + name)
    for name, digest in load(source / 'protected_sha256.json').items():
        require(sha(Path(name)) == digest, 'Protected parent changed: ' + name)
    for name, digest in load(source / 'reused_map_provenance.json').items():
        require(sha(Path(name)) == digest, 'Reused map/PCF/synthesis changed: ' + name)

    route = source / 'work/place_route/top_pnr.adf'
    report = source / 'final_sta/report_timing/top.rtr'
    route_hash, report_hash = sha(route), sha(report)
    require(route_hash == receipt['route_sha256'] and report_hash == receipt['report_sha256'],
            'Recovery route/report changed')
    rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')
    require(len(rows) == 126 and json.loads(json.dumps(rows)) == receipt['timing_rows'], 'Strict 126 STA rows changed')
    analysis = analyze(report)  # Streams the entire report, including detailed paths.
    require(not analysis['violated_paths'] and json.loads(json.dumps(analysis)) == load(source / 'final_sta_analysis.json'),
            'Full timing analysis changed or violated paths exist')
    pin_report = source / 'work/place_route/top_prr.prt'
    actual_pins = validators.pinmap(pin_report)
    require(actual_pins == validators.pinmap(FROZEN / 'routed/top_prr.prt'), 'Pin equality failed')
    # Match the inherited audit's FDC gate against actual candidate inputs.
    for fdc in (source / 'inputs/source/constraints').glob('*.fdc'):
        for line in fdc.read_bytes().decode('ascii', errors='replace').splitlines():
            if line.strip().startswith('#'):
                continue
            m = re.search(r'define_attribute\s+\{p:([^}]+)\}\s+\{(?:PAP_LOC|PAP_IO_LOC)\}\s+\{([^}]+)\}', line)
            if m:
                port, ball = m.groups()
                if port in ('ref_clk_p', 'ref_clk_n'):
                    require(ball == {'ref_clk_p': 'F6', 'ref_clk_n': 'E6'}[port], 'Reference pad changed')
                else:
                    require(port in actual_pins and actual_pins[port][0] == ball, 'FDC ball mismatch: ' + port)
    pin = dict(identical=True, ports=len(actual_pins), report_sha256=sha(pin_report))
    require(pin == load(source / 'pin_audit.json'), 'Saved pin proof changed')
    physical = validators.phy(source / 'routed_phy.txt')
    require(physical == validators.phy(FROZEN / 'routed_phy.txt'), 'PHY equality failed')
    phy = dict(identical=True, actual=physical, route_sha256=route_hash)
    require(json.loads(json.dumps(phy)) == load(source / 'phy_audit.json'), 'Saved PHY proof changed')

    # Confirm successful same-route vendor commands; do not execute them.
    for stage, operation in [('reroute', 'pnr'), ('full_sta', 'report_timing'), ('bitgen', 'gen_bit_stream')]:
        text = (source / (stage + '.log')).read_bytes().decode('gb18030', errors='replace')
        require(not re.search(validators.VENDOR_ERROR, text, re.M | re.I), 'Vendor error: ' + stage)
        input_path = source / ('work/device_map/top_map.adf' if stage == 'reroute' else 'work/place_route/top_pnr.adf')
        require(re.search(r'Executing : ' + operation + r'[^\n]*' + re.escape(input_path.as_posix()) +
                          r'[^\n]*successfully\.', text), 'Successful exact-input command missing: ' + stage)
        require(input_path.as_posix() in (source / (stage + '.tcl')).read_text(), 'Tcl input changed')
    inherited_pnr = (parent / 'strong_pnr.tcl').read_bytes().replace(
        (parent / 'work').as_posix().encode(), (source / 'work').as_posix().encode()).replace(
        b'-max_hold_violated_paths_num 15000', b'-max_hold_violated_paths_num 50000')
    require(inherited_pnr.split() == (source / 'reroute.tcl').read_bytes().split(), 'PNR constraints/options changed')
    bits = list((source / 'bitgen').rglob('*.sbit'))
    bit_hash = sha(source / 'top.sbit')
    require(len(bits) == 1 and sha(bits[0]) == bit_hash == receipt['bit_sha256'], 'Generated bit mismatch')

    utilization = source / 'work/synthesize/apm_drm_lutram_utilization.log'
    raw = utilization.read_bytes()
    routed = (source / 'routed_phy.txt').read_bytes()
    detector = source / 'inputs/source/motion/block_motion_detector.v'
    detector_raw = detector.read_bytes()
    for quote in [b'parameter integer WIDTH = 640', b'parameter integer HEIGHT = 480',
                  b'parameter SAMPLE_STEP = 4', b'reg [7:0] history [0:TOTAL_SAMPLES-1];',
                  b'history_q <= history[sample_address];', b'history[sample_address] <= luma;']:
        require(quote in detector_raw, 'Logical history/read-first source changed')
    old_resource = load(source / 'motion_resource_proof.json')
    require(old_resource['mapped_sha256'] == sha(source / 'work/device_map/top_map.adf') and
            old_resource['synthesized_sha256'] == sha(source / 'work/synthesize/top_syn.adf') and
            old_resource['route_sha256'] == route_hash and old_resource['evidence_sha256'] == sha(utilization),
            'Resource map/route binding changed')
    prefixes = ('ov5640_top', 'cam2_ov5640_top', 'cam3_ov5640_top', 'cam4_ov5640_top')
    expected_histories = {p + '/u_motion_tap/u_detector/history' for p in prefixes}
    require(set(x.decode().lstrip('\\') for x in re.findall(
        rb'([^\s|()]+/u_motion_tap/u_detector/history)(?:_[0-7])?', raw)) == expected_histories,
        'Motion history scope differs from CAM1-4')
    histories = []
    for index, prefix in enumerate(prefixes):
        instance = prefix + '/u_motion_tap/u_detector'
        memory = (instance + '/history').encode()
        start = raw.find(memory)
        require(start >= 0, 'Missing history: ' + prefix)
        block = raw[start:]
        end = block.find(b'|---')
        require(end > 0, 'Missing history table delimiter')
        block = block[:end]
        banks = re.findall(rb'history_([0-7])\s*\|\s*32 K x 1\s*\|\s*READ_BEFORE_WRITE\s*\|\s*/\s*\|\s*SINGLE_PORT\s*\|\s*GTP_DRM36K_E1', block)
        require(sorted(banks) == [str(i).encode() for i in range(8)], 'Eight read-first banks missing')
        physical_banks = []
        for i in range(8):
            bank = memory + b'_' + str(i).encode() + b'/gopdrm_36k'
            match = re.search(rb'\(INSTANNOTATE\s+\(INSTREF\s+\\?' + re.escape(bank) +
                rb'\s*\)\s*\(PLACE\s+impl_drm\s+\(DEVINSTREF\s+DRM\s+\(SITEREF\s+(\d+)\s+(\d+)', routed)
            require(match, 'Missing routed bank: ' + bank.decode())
            physical_banks.append(dict(instance=bank.decode(), site=[int(v) for v in match.groups()]))
        old = old_resource['histories'][index]
        require(old['instance'] == memory.decode() and old['routed_banks'] == physical_banks and
                old['evidence'] == block.decode('ascii', errors='replace'), 'Recovery RAM proof changed')
        histories.append(dict(instance=instance, depth=19200, width=8, mode='read_first',
            physical_bank_depth=32768, physical_banks=8, routed_banks=physical_banks,
            bram_instances=[b['instance'] for b in physical_banks], evidence=[
                dict(file='work/synthesize/apm_drm_lutram_utilization.log', sha256=sha(utilization),
                     quote=block.decode('ascii', errors='replace')),
                dict(file='inputs/source/motion/block_motion_detector.v', sha256=sha(detector),
                     quote='reg [7:0] history [0:TOTAL_SAMPLES-1];')]))
    all_banks = re.findall(rb'\(INSTANNOTATE\s+\(INSTREF\s+\\?([^\s()]+/u_motion_tap/u_detector/history_[0-7]/gopdrm_36k)', routed)
    require(len(all_banks) == 32 and {x.decode() for x in all_banks} ==
            {b for row in histories for b in row['bram_instances']}, 'Routed motion scope differs')
    del routed

    dest = Path(tempfile.mkdtemp(prefix='deploy_evidence_', dir=HERE)).resolve()
    copied = {}

    def copy(original, relative):
        output = dest / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        digest = sha(original)
        shutil.copy2(original, output)
        require(sha(output) == digest == sha(original), 'Copy changed: ' + relative)
        copied[relative] = dict(source=str(original), sha256=digest)

    for name in frozen_inputs:
        copy(source / 'inputs' / name, 'inputs/' + name)
    for original, relative in [(route, 'routed/top_pnr.adf'), (pin_report, 'routed/top_prr.prt'),
            (report, 'final_sta/report_timing/top.rtr'), (source / 'top.sbit', 'top.sbit'),
            (source / 'routed_phy.txt', 'routed_phy.txt'), (utilization, 'work/synthesize/apm_drm_lutram_utilization.log'),
            (source / 'work/device_map/top_map.adf', 'work/device_map/top_map.adf'),
            (source / 'work/device_map/top.pcf', 'work/device_map/top.pcf'),
            (source / 'work/synthesize/top_syn.adf', 'work/synthesize/top_syn.adf'),
            (parent / 'input_sha256.json', 'input_sha256.json')]:
        copy(original, relative)
    for name in ['receipt.json', 'final_sta_proof.json', 'final_sta_analysis.json',
                 'motion_resource_proof.json', 'protected_sha256.json', 'reused_map_provenance.json',
                 'reroute.tcl', 'reroute.log', 'routed_phy.tcl', 'routed_phy.log',
                 'full_sta.tcl', 'full_sta.log', 'bitgen.tcl', 'bitgen.log']:
        copy(source / name, 'original/' + name)
    resource = dict(required_histories=4, bits_per_history=19200*8,
        mapped_sha256=old_resource['mapped_sha256'], synthesized_sha256=old_resource['synthesized_sha256'],
        route_sha256=route_hash, reviewer='prepare_program_evidence.py: direct automated attribution of parent-reviewed recovery',
        histories=histories, review_kind='automated artifact verification; no runtime acceptance')
    save(dest / 'resource_review.json', resource)
    validators.W = dest / 'work'
    validators.resources(dest)  # Unmodified inherited hash/quote/geometry gate.
    save(dest / 'pin_audit.json', pin)
    save(dest / 'phy_audit.json', phy)
    save(dest / 'final_sta_proof.json', dict(route_sha256=route_hash, report_sha256=report_hash, rows=rows,
                                           full_report_violations=0))
    save(dest / 'assembly_provenance.json', dict(source_run=str(source), source_receipt_sha256=sha(source / 'receipt.json'),
        adapter_sha256=sha(Path(__file__)), copied=copied, runtime_acceptance='pending', hardware_operations=0))
    provenance = dict(route_sha256=route_hash, report_sha256=report_hash,
        mapped_sha256=resource['mapped_sha256'], pcf_sha256=sha(dest / 'work/device_map/top.pcf'), bit_sha256=bit_hash,
        source_run=str(source), assembly_provenance_sha256=sha(dest / 'assembly_provenance.json'))
    for key, name in [('resource_proof_sha256', 'resource_proof.json'), ('pin_proof_sha256', 'pin_audit.json'),
                      ('phy_proof_sha256', 'phy_audit.json'), ('input_manifest_sha256', 'input_sha256.json')]:
        provenance[key] = sha(dest / name)
    save(dest / 'bit_provenance.json', provenance)
    status = dict(stage='complete', status='complete', run=str(dest), bit=str(dest / 'top.sbit'),
        bit_sha256=bit_hash, route_sha256=route_hash, report_sha256=report_hash,
        origin='verified assembly of completed recovery, no new vendor build', source_run=str(source),
        runtime_acceptance='pending', hardware_programming='not_performed', flash='untouched')
    save(dest / 'status.json', status)
    programmer = ROOT / 'project/tools/program_100h_motion.py'
    command = [sys.executable, str(programmer), '--mode', 'sram', '--check', '--bit', status['bit'],
               '--build-status', str(dest / 'status.json'), '--log-dir', str(dest / 'checks')]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    (dest / 'readiness_check.stdout.txt').write_bytes(result.stdout)
    require(result.returncode == 0, 'Programmer readiness blocked: ' + result.stdout.decode(errors='replace'))
    print(result.stdout.decode(), end='')
    program_command = [v for v in command if v != '--check']
    program_command[-1] = str(dest / 'program')
    save(dest / 'parent_commands.json', dict(check=command, program_sram=program_command))
    print('EVIDENCE_RUN:', dest)
    print('PROGRAM_SRAM:', subprocess.list2cmdline(program_command))
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, default=HERE / 'recovery_0so0ct0h')
    args = parser.parse_args()
    assemble(args.source_run.resolve(strict=True))
