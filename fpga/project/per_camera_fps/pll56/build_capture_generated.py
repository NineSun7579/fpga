"""Deferred standalone PDS build. --check never starts PDS; parent invokes --run."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from prepare import HERE, ROOT, FROZEN, TOP, check, sha, save

PDS = Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH = 'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
BUSY = {'pds.exe', 'pds_shell.exe', 'pnr.exe', 'ta.exe', 'bitgen.exe', 'pne.exe',
        'ppc.exe', 'ppp.exe', 'cdt_js.exe', 'cdt_cfg.exe', 'cdt_cfg_shell.exe'}

def idle():
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=True, shell=False)
    rows = list(csv.reader(result.stdout.decode('mbcs', errors='replace').splitlines()))
    busy = [row for row in rows if row and row[0].lower() in BUSY]
    if busy:
        raise RuntimeError('Vendor process active: ' + repr(busy))
    return result.stdout

def inherited():
    # Import read-only validators; never call inherited preparation/build/status code.
    # Suppress bytecode so this task writes only its owned directory.
    sys.dont_write_bytecode = True
    parent = ROOT / 'project/motion_100h'
    sys.path.insert(0, str(parent))
    spec = importlib.util.spec_from_file_location('motion_validators', parent / 'build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.path.pop(0)
    return module

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--placement-seed', type=int, default=None)
    args = parser.parse_args()
    assert args.placement_seed is None or args.placement_seed >= 0
    receipt = check()
    candidate_adapter = Path('C:\\Users\\NineSun\\Desktop\\ov56401\\project\\per_camera_fps\\pll56\\capture_candidate\\motion_stream_adapter.v')
    assert sha(candidate_adapter) == '102b5da4a09318ca806ae851b30550a9ecef63f852d3fc43d089fb6fd77cf12d', 'Candidate adapter changed'
    receipt.update(rtl_experiment='Flatten same-edge motion-record capture enable',
                   rtl_override='source/motion/motion_stream_adapter.v',
                   adapter_original_sha256='70960e885ffd390b19594b4cd258ac2de3d47180d7d1fac225e3552134103d22', adapter_candidate_sha256='102b5da4a09318ca806ae851b30550a9ecef63f852d3fc43d089fb6fd77cf12d',
                   capture_simulation_receipt='C:\\Users\\NineSun\\Desktop\\ov56401\\project\\per_camera_fps\\pll56\\sim_capture_tav0mfuo\\receipt.json', capture_simulation_sha256='104820ac2810ec1744e3e79166fc798d7c2acc5532e1203a921ae5f46406d679',
                   runner_source_sha256='8e50b01fb139e9653b992840c1bb84c099f8f758a46ec822f9ca42e51e366323')
    simulations = []
    for file in HERE.glob('sim_*/receipt.json'):
        sim = json.loads(file.read_text())
        log = file.parent / 'simulation.log'
        rom = FROZEN / 'inputs/source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v'
        if (sim.get('status') == 'PASS' and sim.get('emitted_transactions') == 1584
                and sim.get('candidate_top_sha256') == receipt['candidate_top_sha256']
                and sim.get('rom_sha256') == sha(rom)
                and sim.get('testbench_sha256') == sha(HERE / 'tb_config.v')
                and sim.get('log_sha256') == sha(log)):
            simulations.append(file)
    assert simulations, 'Matching passing actual-ROM simulation required; run simulate.py'
    receipt['simulation_receipt'] = str(simulations[-1])
    receipt['simulation_receipt_sha256'] = sha(simulations[-1])
    assert PDS.is_file(), PDS
    if args.check:
        idle()
        print('PASS frozen inputs / candidate / PDS paths / tasklist; NO vendor launch')
        return
    lock = HERE.parent / 'fpga/build.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        idle()
        run = Path(tempfile.mkdtemp(prefix='build_capture_', dir=HERE))
        work = run / 'work'
        work.mkdir()
        receipt.update(status='running', run=str(run), started=time.strftime('%Y-%m-%d %H:%M:%S'),
                       inherited_build_sha256=sha(ROOT / 'project/motion_100h/build.py'),
                       inherited_pnr_script_sha256=sha(FROZEN / 'strong_pnr.tcl'))
        if args.placement_seed is not None:
            receipt.update(recovery_variable='Global Random Seed (Placement)',
                           placement_seed=args.placement_seed,
                           recovery_from=str(HERE / 'build_po3co5wg'),
                           vendor_help_sha256=sha(HERE / 'query_pnr.log'))
        save(run / 'receipt.json', receipt)
        save(HERE / 'current_run.json', receipt)
        print('BUILD_RUN', run, flush=True)
        # Copy frozen inputs byte-for-byte to private storage, protecting original
        # vendor IP even if PDS decides to regenerate auxiliary files beside IDFs.
        for tree in ('source', 'ipcore'):
            shutil.copytree(FROZEN / 'inputs' / tree, run / 'inputs' / tree)
        (run / 'inputs/source/top.v').write_bytes(TOP.read_bytes())
        (run / 'inputs/source/motion/motion_stream_adapter.v').write_bytes(candidate_adapter.read_bytes())
        (run / 'inputs/source/constraints/clock.fdc').write_bytes((HERE / 'source/constraints/clock.fdc').read_bytes())
        expected = {p.relative_to(run / 'inputs').as_posix(): sha(p)
                    for p in (run / 'inputs').rglob('*') if p.is_file()}
        save(run / 'input_sha256.json', expected)
        raw = (HERE / 'cloned.pds').read_bytes()
        raw = raw.replace((FROZEN / 'inputs').as_posix().encode(), (run / 'inputs').as_posix().encode())
        raw = raw.replace(TOP.as_posix().encode(), (run / 'inputs/source/top.v').as_posix().encode())
        raw = raw.replace((HERE / 'source/constraints/clock.fdc').as_posix().encode(), (run / 'inputs/source/constraints/clock.fdc').as_posix().encode())
        for path in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', raw):
            resolved = Path(path.decode('ascii')).resolve()
            assert (run / 'inputs') in resolved.parents and resolved.is_file(), resolved
        (work / 'project.pds').write_bytes(raw)
        (work / 'flow.pds').write_bytes(raw)
        receipt['runtime_project_sha256'] = sha(work / 'project.pds')
        validators = inherited()

        def verify():
            check()
            assert sha(candidate_adapter) == receipt['adapter_candidate_sha256']
            for name, digest in expected.items():
                assert sha(run / 'inputs' / name) == digest, 'Private input modified: ' + name

        def execute(stage, command, cwd):
            verify()
            tasklog = idle()
            (run / (stage + '.tasklist.csv')).write_bytes(tasklog)
            receipt['stage'] = stage
            receipt['stage_started'] = time.strftime('%Y-%m-%d %H:%M:%S')
            print('STAGE', stage, str(run), receipt['stage_started'], flush=True)
            receipt.setdefault('commands', {})[stage] = [str(x) for x in command]
            save(run / 'receipt.json', receipt)
            save(HERE / 'current_run.json', receipt)
            with (run / (stage + '.log')).open('xb') as stream:
                proc = subprocess.Popen([str(x) for x in command], cwd=cwd, shell=False,
                                        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                receipt['vendor_pid'] = proc.pid
                save(run / 'receipt.json', receipt)
                print('VENDOR_PID', proc.pid, flush=True)
                code = proc.wait()
            text = (run / (stage + '.log')).read_bytes().decode('gb18030', errors='replace')
            if code or re.search(validators.VENDOR_ERROR, text, re.M | re.I):
                raise RuntimeError('PDS failed at ' + stage + ' returncode=' + str(code))
            verify()
            receipt.setdefault('completed_stages', {})[stage] = time.strftime('%Y-%m-%d %H:%M:%S')
            save(run / 'receipt.json', receipt)
            save(HERE / 'current_run.json', receipt)
            print('STAGE_FINISHED', stage, receipt['completed_stages'][stage], flush=True)

        def action(stage, body, cwd):
            cwd.mkdir(exist_ok=True)
            script = run / (stage + '.tcl')
            script.write_text(body, encoding='ascii')
            execute(stage, [PDS, '-file', script, '-work_dir', cwd, '-project_name', stage], cwd)

        for stage in ('compile', 'synthesize', 'dev_map'):
            execute(stage, [PDS, '-project', work / 'flow.pds', '-run', stage, '-work_dir', work], work)
        script = (FROZEN / 'strong_pnr.tcl').read_bytes().decode('ascii')
        oldwork = (ROOT / 'project/motion_100h/work').as_posix()
        assert script.count(oldwork) == 2
        script = script.replace(oldwork, work.as_posix())
        assert script.count('add_constraint -physical -pcf') == 1
        assert script.count('-max_hold_violated_paths_num 15000') == 1
        assert 'input_place_db_file' not in script
        script = script.replace('-max_hold_violated_paths_num 15000', '-max_hold_violated_paths_num 50000')
        if args.placement_seed is not None:
            assert '-gplace_seed' not in script
            script = script.replace('pnr -input_db_file', 'pnr -gplace_seed ' + str(args.placement_seed) + ' -input_db_file')
        action('strong_pnr', script, work)
        route = work / 'place_route/top_pnr.adf'
        route_sha = sha(route)
        receipt['stage'] = 'pin_verification'
        save(run / 'receipt.json', receipt)
        actual_pins = validators.pinmap(work / 'place_route/top_prr.prt')
        reference_pins = validators.pinmap(FROZEN / 'routed/top_prr.prt')
        assert len(actual_pins) == len(reference_pins) == 112, 'Incomplete pin evidence'
        assert actual_pins == reference_pins, 'Routed pins changed'
        save(run / 'pin_audit.json', dict(status='PASS', ports=112, identical=True,
                                        report_sha256=sha(work / 'place_route/top_prr.prt')))
        action('routed_phy', ARCH + '.switch_db -input {' + route.as_posix() +
               '} -output {' + (run / 'routed_phy.txt').as_posix() + '}\n', run / 'routed_phy')
        assert validators.phy(run / 'routed_phy.txt') == validators.phy(FROZEN / 'routed_phy.txt'), 'HSST placement/pads changed'
        save(run / 'phy_audit.json', dict(status='PASS', identical=True,
                                        actual=validators.phy(run / 'routed_phy.txt'), route_sha256=route_sha))
        receipt['stage'] = 'motion_resource_verification'
        save(run / 'receipt.json', receipt)
        resource = work / 'synthesize/apm_drm_lutram_utilization.log'
        raw = resource.read_bytes()
        histories = []
        routed_text = (run / 'routed_phy.txt').read_bytes()
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
        save(run / 'motion_resource_proof.json', dict(histories=histories, evidence_sha256=sha(resource),
             mapped_sha256=sha(work / 'device_map/top_map.adf'), synthesized_sha256=sha(work / 'synthesize/top_syn.adf'), route_sha256=route_sha,
             note='Physical 32K banks implement the unchanged logical 19200-byte history; Detector/history RTL preserved; only adapter capture predicate rewritten; map built afresh for PLL56.'))
        assert sum(h['physical_banks'] for h in histories) == 32
        receipt['motion_resources'] = 'PASS'
        action('full_sta', ARCH + 'report_timing -input_db_file {' + route.as_posix() +
               '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n', run / 'final_sta')
        report = run / 'final_sta/report_timing/top.rtr'
        receipt['stage'] = 'final_timing_verification'
        save(run / 'receipt.json', receipt)
        save(HERE / 'current_run.json', receipt)
        from diagnose_timing import diagnose
        diagnosis = diagnose(run)
        receipt.update(timing_rows=len(diagnosis['summary_rows']),
                       timing_failing_rows=diagnosis['failing_rows'],
                       final_sta_analysis_sha256=sha(run / 'final_sta_analysis.json'),
                       pin_equivalence='PASS', phy_equivalence='PASS', bitgen_run=False)
        save(run / 'receipt.json', receipt)
        save(HERE / 'current_run.json', receipt)
        rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')
        assert len(rows) == 126, 'Incomplete multi-corner timing rows'
        from audit import strict_timing, constraints
        save(run / 'strict_timing.json', strict_timing(report))
        save(run / 'clock_audit.json', constraints(report, FROZEN / 'final_sta/report_timing/top.rtr'))
        assert sha(route) == route_sha
        receipt.update(route_sha256=route_sha, timing_report_sha256=sha(report), timing_rows=rows,
                       pin_equivalence='PASS', phy_equivalence='PASS',
                       mapped_sha256=sha(work / 'device_map/top_map.adf'),
                       synthesized_sha256=sha(work / 'synthesize/top_syn.adf'),
                       physical_constraints_sha256=sha(work / 'device_map/top.pcf'))
        # Retain complete synthesis/map/route reports for area and motion review.
        receipt['area_reports'] = {p.relative_to(run).as_posix(): sha(p)
                                   for p in work.rglob('*') if p.is_file() and
                                   p.suffix.lower() in ('.rpt', '.rtr', '.txt', '.log', '.prr')}
        assert receipt['area_reports'], 'Missing area/report evidence'
        receipt['motion_resource_review'] = 'PASS new candidate synthesis/map and 32 routed banks'
        save(run / 'receipt.json', receipt)
        action('bitgen', ARCH + 'gen_bit_stream -input_db_file {' + route.as_posix() +
               '} -force_to_run -create_bit_file TRUE\n', run / 'bitgen')
        bits = list((run / 'bitgen').rglob('*.sbit'))
        assert len(bits) == 1 and bits[0].stat().st_size and sha(route) == route_sha
        assert sha(report) == receipt['timing_report_sha256']
        shutil.copy2(bits[0], run / 'top.sbit')
        receipt.update(status='built_for_parent_review', bit_sha256=sha(run / 'top.sbit'),
                       finished=time.strftime('%Y-%m-%d %H:%M:%S'), bitgen_run=True)
        verify()
        print('BUILD_ARTIFACT ' + str(run / 'top.sbit'))
    except Exception as error:
        if 'run' in locals():
            receipt.update(status='failed', error=str(error), error_stage=receipt.get('stage'), finished=time.strftime('%Y-%m-%d %H:%M:%S'))
            print('BUILD_FAILED', receipt.get('stage'), str(error), flush=True)
        raise
    finally:
        if 'run' in locals():
            receipt['log_sha256'] = {p.name: sha(p) for p in run.glob('*.log')}
            save(run / 'receipt.json', receipt)
            save(HERE / 'current_run.json', receipt)
            print('BUILD_RECEIPT', run / 'receipt.json', flush=True)
        lock.unlink()

if __name__ == '__main__':
    main()
