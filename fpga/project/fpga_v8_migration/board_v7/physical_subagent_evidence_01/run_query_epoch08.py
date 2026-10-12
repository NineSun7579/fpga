"""Wait for the existing exporter, then run one isolated importer probe."""
from pathlib import Path
import subprocess, time, json, hashlib, traceback
from native_query08 import idle, PDS, BASE
from prepare_query_epoch08 import main as prepare, OUT

def main():
    while True:
        try:
            idle()
            # The exporter may be between its two sequential calls.
            r=subprocess.run(['powershell','-NoProfile','-Command',
                "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -match 'probe_native_objects.py'} | Select-Object -ExpandProperty ProcessId"],capture_output=True,check=True)
            if not r.stdout.strip(): break
        except AssertionError:
            pass
        time.sleep(5)
    evidence=BASE/'fixed_06/native_probe_07/input_hashes.json'
    assert evidence.exists(), 'Exporter did not finish successfully; preserving failure'
    prepare()
    project=OUT/'query_epoch08.pds'
    guard=json.loads((BASE.parent/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    bad=[p for p,h in guard.items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not bad,bad
    cmd=[PDS,'-project',str(project),'-run','synthesize','-work_dir',str(OUT)]
    (OUT/'launch.json').write_text(json.dumps({'command':cmd,'protected_count':len(guard),'bit_permitted':False},indent=2))
    idle()
    with (OUT/'shell.log').open('xb') as f:
        result=subprocess.run(cmd,cwd=OUT,stdout=f,stderr=subprocess.STDOUT)
    raw=(OUT/'shell.log').read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    (OUT/'shell.txt').write_text(text,encoding='utf8')
    lines=text.splitlines()
    findings=[s for s in lines if 'NATIVE_QUERY08' in s or s.startswith('E:')]
    (OUT/'result.json').write_text(json.dumps({'exit_code':result.returncode,'query_evidence':findings,'acceptance':False},indent=2))
    print('\n'.join(findings),flush=True)

if __name__=='__main__':
    try: main()
    except BaseException:
        failure=BASE/'fixed_06/query_epoch08_runner_failure.txt'
        assert not failure.exists()
        failure.write_text(traceback.format_exc(),encoding='utf8')
        raise
