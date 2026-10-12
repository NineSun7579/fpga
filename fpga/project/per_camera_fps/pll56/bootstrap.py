"""Derive standalone scripts with checked byte edits; never mutate parent inputs."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PATTERN = HERE.parent / 'fpga'

def replace(raw, old, new, count=1):
    assert raw.count(old) == count, (old, raw.count(old))
    return raw.replace(old, new)

def write(name, raw):
    path = HERE / name
    if path.exists():
        assert path.read_bytes() == raw, name
        return
    with path.open('xb') as out:
        out.write(raw)

raw = (PATTERN / 'prepare.py').read_bytes()
raw = replace(raw, b"new = block.replace(b'.TOTAL_V_PIXEL   (12\\'d984)', b'.TOTAL_V_PIXEL   (12\\'d843)')",
              b"new = block.replace(b'.SENSOR_PLL_MULT (8\\'h30)', b'.SENSOR_PLL_MULT (8\\'h38)')")
raw = replace(raw, b'assert changed == [1571, 1672], changed', b'assert len(changed) == 2, changed')
raw = replace(raw, b"assert result.replace(b'.TOTAL_V_PIXEL   (12\\'d843)', b'.TOTAL_V_PIXEL   (12\\'d984)') == raw",
              b"assert result.replace(b'.SENSOR_PLL_MULT (8\\'h38)', b'.SENSOR_PLL_MULT (8\\'h30)') == raw")
raw = replace(raw, b"elif name.startswith(('../source/', '../ipcore/')):",
              b"elif name == '../source/constraints/clock.fdc':\n            path = HERE / 'source/constraints/clock.fdc'\n        elif name.startswith(('../source/', '../ipcore/')):")
raw = replace(raw, b'def main():', b'''def clocks():
    raw = (FROZEN / 'inputs/source/constraints/clock.fdc').read_bytes()
    result = raw
    for cam in (3, 4):
        token = ('create_clock -name {cmos%d_pclk} [get_ports {cmos%d_pclk}] -period {20.833} -waveform {0.000 10.416}' % (cam, cam)).encode()
        assert result.count(token) == 1
        result = result.replace(token, token.replace(b'{20.833}', b'{17.857}').replace(b'10.416', b'8.9285'))
    assert result.replace(b'{17.857}', b'{20.833}').replace(b'8.9285', b'10.416') == raw
    return result

def main():''')
raw = replace(raw, b"TOP.parent.mkdir(exist_ok=True)", b"TOP.parent.mkdir(exist_ok=True)\n    constraint = HERE / 'source/constraints/clock.fdc'\n    constraint.parent.mkdir(exist_ok=True)\n    if not constraint.exists():\n        constraint.write_bytes(clocks())")
raw = replace(raw, b"assert TOP.read_bytes() == raw", b"assert TOP.read_bytes() == raw\n    assert (HERE / 'source/constraints/clock.fdc').read_bytes() == clocks()")
raw = replace(raw, b"'constraint_sha256': {k: v for k, v in inputs.items() if k.startswith('source/constraints/')},", b"'constraint_sha256': {k: (sha(HERE / k) if k == 'source/constraints/clock.fdc' else v) for k, v in inputs.items() if k.startswith('source/constraints/')},\n            'clock_change': 'Only CAM3/4 port periods 20.833 -> 17.857 ns; waveform half-period 8.9285 ns',")
write('prepare.py', raw)

raw = (PATTERN / 'simulate.py').read_bytes()
raw = replace(raw, b"print('SKIP ModelSim unavailable')\n        return", b"raise RuntimeError('ModelSim unavailable; build blocked')")
write('simulate.py', raw)

raw = (PATTERN / 'tb_config.v').read_bytes()
raw = replace(raw, b"#(.SENSOR_PLL_MULT(8'h30)) old_cam34", b"#(.SENSOR_PLL_MULT(8'h54)) cam2")
raw = replace(raw, b"#(.SENSOR_PLL_MULT(8'h30)) rom", b"#(.SENSOR_PLL_MULT(8'h38)) rom")
raw = replace(raw, b".total_v_pixel(13'd843)", b".total_v_pixel(13'd984)")
raw = replace(raw, b'''if(data[j]!==24'h303630) fail("PLL 48 MHz multiplier");
   ''', b'''if(j==1 && data[j]!==24'h303654) fail("CAM2 PLL 84 MHz multiplier");
     if(j>=2 && data[j]!==24'h303638) fail("CAM34 PLL 56 MHz multiplier");
   ''')
raw = replace(raw, b'''end else if(j>=2 && index==230) begin
    if(data[j]!==24'h380f4b) fail("candidate VTS low");
   ''', b'')
raw = replace(raw, b'230: if(j<2 &&', b'230: if(')
raw = replace(raw, b'VTS 984=03d8 / 843=034b; 640x480; PLL unchanged', b'VTS 984=03d8 all cameras; 640x480; CAM12 PLL54 CAM34 PLL38')
write('tb_config.v', raw)

raw = (PATTERN / 'build_later.py').read_bytes()
raw = replace(raw, b"lock = HERE / 'build.lock'", b"lock = HERE.parent / 'fpga/build.lock'")
raw = replace(raw, b"(run / 'inputs/source/top.v').write_bytes(TOP.read_bytes())", b"(run / 'inputs/source/top.v').write_bytes(TOP.read_bytes())\n        (run / 'inputs/source/constraints/clock.fdc').write_bytes((HERE / 'source/constraints/clock.fdc').read_bytes())")
raw = replace(raw, b"raw = raw.replace(TOP.as_posix().encode(), (run / 'inputs/source/top.v').as_posix().encode())", b"raw = raw.replace(TOP.as_posix().encode(), (run / 'inputs/source/top.v').as_posix().encode())\n        raw = raw.replace((HERE / 'source/constraints/clock.fdc').as_posix().encode(), (run / 'inputs/source/constraints/clock.fdc').as_posix().encode())")
raw = replace(raw, b"script = script.replace(oldwork, work.as_posix())", b"script = script.replace(oldwork, work.as_posix())\n        assert script.count('add_constraint -physical -pcf') == 1\n        assert script.count('-max_hold_violated_paths_num 15000') == 1\n        assert 'input_place_db_file' not in script\n        script = script.replace('-max_hold_violated_paths_num 15000', '-max_hold_violated_paths_num 50000')")
raw = replace(raw, b"assert actual_pins == reference_pins, 'Routed pins changed'", b"assert len(actual_pins) == len(reference_pins) == 112, 'Incomplete pin evidence'\n        assert actual_pins == reference_pins, 'Routed pins changed'")
# Inherit the exact resource attribution gate as code, using this new synthesis/map/route.
recovery = (PATTERN / 'timing_recovery.py').read_bytes()
start = recovery.index(b"        resource = work / 'synthesize/apm_drm_lutram_utilization.log'")
end = recovery.index(b"        action('full_sta'", start)
gate = recovery[start:end].replace(b'dest', b'run').replace(b'route_hash', b'route_sha')
gate = gate.replace(b"sha(mapped)", b"sha(work / 'device_map/top_map.adf')").replace(b"sha(synthesis)", b"sha(work / 'synthesize/top_syn.adf')")
gate = gate.replace(b'RTL and map reused exactly.', b'RTL preserved and map built afresh for PLL56.')
raw = replace(raw, b"        action('full_sta', ARCH", gate + b"        assert sum(h['physical_banks'] for h in histories) == 32\n        receipt['motion_resources'] = 'PASS'\n        action('full_sta', ARCH")
raw = replace(raw, b"rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')", b"rows = validators.timing(report, FROZEN / 'routed/top_timing_summary_after_hold_fix.txt')\n        assert len(rows) == 126, 'Incomplete multi-corner timing rows'\n        from audit import strict_timing\n        save(run / 'strict_timing.json', strict_timing(report))")
raw = replace(raw, b"receipt['motion_resource_review'] = 'Required on candidate synthesis/map before deployment; baseline review is not reused'", b"receipt['motion_resource_review'] = 'PASS new candidate synthesis/map and 32 routed banks'")
raw = replace(raw, b"receipt['stage'] = stage", b"receipt['stage'] = stage\n            receipt['stage_started'] = time.strftime('%Y-%m-%d %H:%M:%S')\n            print('STAGE', stage, str(run), receipt['stage_started'], flush=True)")
raw = replace(raw, b"                code = proc.wait()", b"                receipt['vendor_pid'] = proc.pid\n                save(run / 'receipt.json', receipt)\n                print('VENDOR_PID', proc.pid, flush=True)\n                code = proc.wait()")
raw = replace(raw, b"raise RuntimeError('PDS failed at ' + stage)", b"raise RuntimeError('PDS failed at ' + stage + ' returncode=' + str(code))")
raw = replace(raw, b"            verify()\n\n        def action", b"            verify()\n            receipt.setdefault('completed_stages', {})[stage] = time.strftime('%Y-%m-%d %H:%M:%S')\n            save(run / 'receipt.json', receipt)\n            print('STAGE_FINISHED', stage, receipt['completed_stages'][stage], flush=True)\n\n        def action")
raw = replace(raw, b"receipt.update(status='failed', error=str(error))", b"receipt.update(status='failed', error=str(error), error_stage=receipt.get('stage'), finished=time.strftime('%Y-%m-%d %H:%M:%S'))\n            print('BUILD_FAILED', receipt.get('stage'), str(error), flush=True)")
raw = replace(raw, b"save(run / 'receipt.json', receipt)\n        lock.unlink()", b"save(run / 'receipt.json', receipt)\n            save(HERE / 'current_run.json', receipt)\n            print('BUILD_RECEIPT', run / 'receipt.json', flush=True)\n        lock.unlink()")
raw = replace(raw, b"save(run / 'receipt.json', receipt)\n        # Copy frozen", b"save(run / 'receipt.json', receipt)\n        save(HERE / 'current_run.json', receipt)\n        print('BUILD_RUN', run, flush=True)\n        # Copy frozen")
write('build_later.py', raw)
