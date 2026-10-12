"""Run a single isolated RTL experiment under the existing strict build gates."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CAND = HERE / 'capture_candidate'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    sys.dont_write_bytecode = True
    candidate = CAND / 'motion_stream_adapter.v'
    preparation = json.loads((CAND / 'preparation.json').read_bytes())
    assert sha(candidate) == preparation['candidate_sha256']
    assert preparation['boolean_cases'] == 128
    passing = []
    for p in HERE.glob('sim_capture_*/receipt.json'):
        sim = json.loads(p.read_bytes())
        if (sim.get('status') == 'PASS' and sim.get('candidate_sha256') == sha(candidate)
                and sim.get('original_sha256') == sha(Path(preparation['original']))
                and sim.get('log_sha256') == sha(p.parent / 'simulation.log')):
            passing.append(p)
    assert passing, 'Matching full-frame/cycle-equivalence ModelSim receipt required'
    simulation = passing[-1]
    upstream = HERE / 'build_later.py'
    text = upstream.read_bytes().decode('utf-8')
    # This generated runner imports the authoritative frozen-input checks. Its
    # only source overlay is the explicitly hashed adapter after private copy.
    replacement = '''    receipt = check()
    candidate_adapter = Path(%r)
    assert sha(candidate_adapter) == %r, 'Candidate adapter changed'
    receipt.update(rtl_experiment='Flatten same-edge motion-record capture enable',
                   rtl_override='source/motion/motion_stream_adapter.v',
                   adapter_original_sha256=%r, adapter_candidate_sha256=%r,
                   capture_simulation_receipt=%r, capture_simulation_sha256=%r,
                   runner_source_sha256=%r)
''' % (str(candidate), sha(candidate), preparation['original_sha256'], sha(candidate),
       str(simulation), sha(simulation), sha(upstream))
    assert text.count('    receipt = check()\n') == 1
    text = text.replace('    receipt = check()\n', replacement)
    assert text.count("tempfile.mkdtemp(prefix='build_', dir=HERE)") == 1
    text = text.replace("tempfile.mkdtemp(prefix='build_', dir=HERE)",
                        "tempfile.mkdtemp(prefix='build_capture_', dir=HERE)")
    overlay_at = "        (run / 'inputs/source/top.v').write_bytes(TOP.read_bytes())\n"
    assert text.count(overlay_at) == 1
    text = text.replace(overlay_at, overlay_at +
        "        (run / 'inputs/source/motion/motion_stream_adapter.v').write_bytes(candidate_adapter.read_bytes())\n")
    assert text.count('        def verify():\n            check()\n') == 1
    text = text.replace('        def verify():\n            check()\n',
        '        def verify():\n            check()\n            assert sha(candidate_adapter) == receipt[\'adapter_candidate_sha256\']\n')
    text = text.replace('RTL preserved and map built afresh for PLL56.',
                        'Detector/history RTL preserved; only adapter capture predicate rewritten; map built afresh for PLL56.')
    # Keeping this generated copy adjacent to upstream preserves imported HERE
    # paths and validators. No baseline script or source file is modified.
    runner = HERE / 'build_capture_generated.py'
    runner.write_text(text, encoding='utf-8')
    receipt_path = CAND / 'launch_receipt.json'
    log = CAND / ('build_launch_' + time.strftime('%Y%m%d_%H%M%S') + '.log')
    receipt = dict(status='starting', started=time.strftime('%Y-%m-%d %H:%M:%S'),
                   candidate_sha256=sha(candidate), simulation_receipt=str(simulation),
                   generated_runner_sha256=sha(runner), inherited_runner_sha256=sha(upstream),
                   placement_seed=1, log=str(log))
    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    save()
    code = 1
    try:
        with log.open('xb') as stream:
            process = subprocess.Popen([sys.executable,'-B','-u',str(runner),'--run','--placement-seed','1'],
                cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            receipt.update(status='running', supervisor_child_pid=process.pid)
            save()
            for line in iter(process.stdout.readline,b''):
                stream.write(line); stream.flush()
                print(line.decode('gb18030','replace').rstrip(),flush=True)
            code = process.wait()
        current = json.loads((HERE/'current_run.json').read_bytes())
        if current.get('started','') >= receipt['started']:
            receipt['build'] = current
    finally:
        receipt.update(status='finished' if code == 0 else 'failed', returncode=code,
                       finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        save()
        print('CAPTURE_BUILD_FINISHED',receipt['status'],receipt_path,flush=True)
    sys.exit(code)

if __name__ == '__main__':
    main()
