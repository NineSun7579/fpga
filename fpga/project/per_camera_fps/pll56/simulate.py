"""Run only the actual configuration ROM in a fresh private ModelSim directory."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from prepare import HERE, FROZEN, check, save, sha

def main():
    receipt = check()
    bindir = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
    tools = {name: bindir / (name + '.exe') for name in ('vlib', 'vlog', 'vsim')}
    if not all(p.is_file() for p in tools.values()):
        raise RuntimeError('ModelSim unavailable; build blocked')
    work = Path(tempfile.mkdtemp(prefix='sim_', dir=HERE))
    rom = FROZEN / 'inputs/source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v'
    commands = [[tools['vlib'], 'work'], [tools['vlog'], '-sv', rom, HERE / 'tb_config.v'],
                [tools['vsim'], '-c', 'work.tb_config', '-do', 'onerror {quit -code 1}; run -all; quit -code 0']]
    logs = []
    for command in commands:
        result = subprocess.run([str(x) for x in command], cwd=work, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90, shell=False)
        logs.append(result.stdout)
        (work / 'simulation.log').write_bytes(b'\n'.join(logs))
        if result.returncode:
            raise RuntimeError('ModelSim failed; see ' + str(work))
    text = b'\n'.join(logs)
    assert b'PASS CONFIG_ROM' in text and b'FAIL ' not in text
    assert text.count(b'EMIT profile=') == 1584
    receipt.update(status='PASS', work_directory=str(work), rom_sha256=sha(rom),
                   testbench_sha256=sha(HERE / 'tb_config.v'), log_sha256=sha(work / 'simulation.log'),
                   emitted_transactions=1584, scope='Actual ROM dynamic simulation; parent parameter propagation checked statically')
    save(work / 'receipt.json', receipt)
    print('PASS 1584 actual ROM transactions; receipt: ' + str(work / 'receipt.json'))

if __name__ == '__main__':
    main()
