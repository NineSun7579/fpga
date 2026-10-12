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
    args = parser.parse_args()
    receipt = check()
    simulations = []
    for file in HERE.glob('sim_*/receipt.json'):
        sim = json.loads(file.read_text())
        log = file.parent / 'simulation.log'
        rom = FROZEN / 'inputs/source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v'
        if (sim.get('status') == 'PASS' and sim.get('emitted_transactions') == 1056
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
    lock = HERE / 'build.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        idle()
        run = Path(tempfile.mkdtemp(prefix='build_', dir=HERE))
        work = run / 'work'
        work.mkdir()
        receipt.update(status='running', run=str(run), started=time.strftime('%Y-%m-%d %H:%M:%S'),
                       inherited_build_sha256=sha(ROOT / 'project/motion_100h/build.py'),
                       inherited_pnr_script_sha256=sha(FROZEN / 'strong_pnr.tcl'))
        save(run / 'receipt.json', receipt)
        # Copy frozen inputs byte-for-byte to private storage, protecting original
        # vendor IP even if PDS decides to regenerate auxiliary files beside IDFs.
        for tree in ('source', 'ipcore'):
            shutil.copytree(FROZEN / 'inputs' / tree, run / 'inputs' / tree)
        (run / 'inputs/source/top.v').write_bytes(TOP.read_bytes())
        expected = {p.relative_to(run / 'inputs').as_posix(): sha(p)
                    for p in (run / 'inputs').rglob('*') if p.is_file()}
        save(run / 'input_sha256.json', expected)
        raw = (HERE / 'cloned.pds').read_bytes()
        raw = raw.replace((FROZEN / 'inputs').as_posix().encode(), (run / 'inputs').as_posix().encode())
        raw = raw.replace(TOP.as_posix().encode(), (run / 'inputs/source/top.v').as_posix().encode())
        for path in re.findall(rb'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', raw):
            resolved = Path(path.decode('ascii')).resolve()
            assert (run / 'inputs') in resolved.parents and resolved.is_file(), resolved
        (work / 'project.pds').write_bytes(raw)
        (work / 'flow.pds').write_bytes(raw)
        receipt['runtime_project_sha256'] = sha(work / 'project.pds')
        validators = inherited()

        def verify():
            check()
            for name, digest in expected.items():
                assert sha(run / 'inputs' / name) == digest, 'Private input modified: ' + name

        def execute(stage, command, cwd):
            verify()
            tasklog = idle()
            (run / (stage + '.tasklist.csv')).write_bytes(tasklog)
            receipt['stage'] = stage
            receipt.setdefault('commands', {})[stage] = [str(x) for x in command]
            save(run / 'receipt.json', receipt)
            with (run / (stage + '.log')).open('xb') as stream:
                proc = subprocess.Popen([str(x) for x in command], cwd=cwd, shell=False,
                                        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                code = proc.wait()
            text = (run / (stage + '.log')).read_bytes().decode('gb18030', errors='replace')
            if code or re.search(validators.VENDOR_ERROR, text, re.M | re.I):
                raise RuntimeError('PDS failed at ' + stage)
            verify()

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
        action('strong_pnr', script, work)
        route = work / 'place_route/top_pnr.adf'
        route_sha = sha(route)
        actual_pins = validators.pinmap(work / 'place_route/top_prr.prt')
        reference_pins = validators.pinmap(FROZEN / 'routed/top_prr.prt')
        assert actual_pins == reference_pins, 'Routed pins changed'
        action('routed_phy', ARCH + '.switch_db -input {' + route.as_posix() +
               '} -output {' + (run / 'routed_phy.txt').as_posix() + '}\n', run / 'routed_phy')
        assert validators.phy(run / 'routed_phy.txt') == validators.phy(FROZEN / 'routed_phy.txt'), 'HSST placement/pads changed'
        action('full_sta', ARCH + 'report_timing -input_db_file {' + route.as_posix() +
               '} -force_to_run -delay_type min_max -nworst 1 -max_path 15000 -input_pins TRUE -report_exception TRUE\n', run / 'final_sta')
        report = run / 'final_sta/report_timing/top.rtr'
        rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')
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
        receipt['motion_resource_review'] = 'Required on candidate synthesis/map before deployment; baseline review is not reused'
        save(run / 'receipt.json', receipt)
        action('bitgen', ARCH + 'gen_bit_stream -input_db_file {' + route.as_posix() +
               '} -force_to_run -create_bit_file TRUE\n', run / 'bitgen')
        bits = list((run / 'bitgen').rglob('*.sbit'))
        assert len(bits) == 1 and bits[0].stat().st_size and sha(route) == route_sha
        assert sha(report) == receipt['timing_report_sha256']
        shutil.copy2(bits[0], run / 'top.sbit')
        receipt.update(status='built_for_parent_review', bit_sha256=sha(run / 'top.sbit'),
                       finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        verify()
        print('BUILD_ARTIFACT ' + str(run / 'top.sbit'))
    except Exception as error:
        if 'run' in locals():
            receipt.update(status='failed', error=str(error))
        raise
    finally:
        if 'run' in locals():
            receipt['log_sha256'] = {p.name: sha(p) for p in run.glob('*.log')}
            save(run / 'receipt.json', receipt)
        lock.unlink()

if __name__ == '__main__':
    main()
