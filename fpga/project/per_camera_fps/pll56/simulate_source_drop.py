"""Meaningful integration equivalence for the extracted source-drop counter."""
from pathlib import Path
import json
import subprocess
import sys
import time
from counter_experiment import HERE, sha, save

def main():
    out = Path(sys.argv[1]).resolve()
    prep = json.loads((out/'preparation.json').read_bytes())
    candidate = Path(prep['candidate'])
    original = Path(prep['original'])
    assert sha(candidate)==prep['candidate_sha256']
    assert sha(original)==prep['original_sha256']
    model = Path('C:/modeltech64_10.6e/win64')
    test = HERE/'tb_source_drop_equivalence.v'
    work = out/'simulation'
    work.mkdir()
    receipt = dict(status='running', started=time.strftime('%Y-%m-%d %H:%M:%S'),
        candidate_sha256=sha(candidate), original_sha256=sha(original),
        testbench_sha256=sha(test), fifo_model='identical controlled interface model; production FIFO unchanged')
    save(work/'receipt.json',receipt)
    try:
        cmds = [[model/'vlib.exe','work'],
            [model/'vlog.exe','-sv',candidate,out/'ov5640_cdc_reference.v',test],
            [model/'vsim.exe','-c','-voptargs=+acc','work.tb_source_drop_equivalence','-do',
             'onerror {quit -code 1 -force}; onbreak {quit -code 1 -force}; run -all; quit -code 0 -force']]
        with (work/'simulation.log').open('xb') as log:
            for cmd in cmds:
                print('SIM_STAGE',cmd[0].name,work,flush=True)
                result=subprocess.run([str(x) for x in cmd],cwd=work,stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=120)
                log.write(result.stdout);log.flush()
                assert result.returncode==0, result.stdout.decode('gb18030','replace')[-3000:]
        output=(work/'simulation.log').read_bytes()
        assert b'PASS SOURCE_DROP_EQUIVALENCE' in output
        assert b'** Error' not in output and b'** Fatal' not in output
        receipt.update(status='PASS',log_sha256=sha(work/'simulation.log'),
            scope='Every source/destination clock edge: source state, 96-bit snapshot, toggle/data pipeline, debug/video outputs; full 307200-pixel offered frame, valid/full coincidence, wrap, resets, restart')
        print(output.decode('gb18030','replace')[-1800:],flush=True)
    except Exception as e:
        receipt.update(status='failed',error=str(e))
        raise
    finally:
        receipt['finished']=time.strftime('%Y-%m-%d %H:%M:%S')
        save(work/'receipt.json',receipt)

if __name__=='__main__':
    main()
