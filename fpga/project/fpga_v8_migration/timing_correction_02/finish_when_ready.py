"""Attach to the existing flow process completion event, without polling."""
import ctypes,json,subprocess,sys
from ctypes import wintypes
from pathlib import Path
from run_whole import WORK
HERE=Path(__file__).resolve().parent
def main():
    pid=int(sys.argv[1])
    marker=WORK/'finish_pipeline_started.json'
    assert not marker.exists(),'One completion pipeline only'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    # Hold the kernel process handle before inspecting identity, preventing PID
    # reuse from turning the subsequent event wait into an unrelated attachment.
    handle=kernel.OpenProcess(0x100000,False,pid)
    if handle:
        cmd=['powershell.exe','-NoProfile','-Command',
             'Get-CimInstance Win32_Process -Filter "ProcessId='+str(pid)+'" | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress']
        check=subprocess.run(cmd,capture_output=True,check=True)
        info=json.loads(check.stdout or 'null')
        if info is not None:
            assert info['Name'].lower()=='python.exe' and 'run_whole.py' in info['CommandLine'],info
        else:
            assert kernel.WaitForSingleObject(handle,0)==0,'Flow identity unavailable'
    else:
        assert (WORK/'baseline_guard.json').exists(),'Flow process unavailable before completion'
        info={'ProcessId':pid,'already_finished':True}
    marker.write_text(json.dumps({'flow_process':info,'wait_method':'Windows process completion event; no polling','programming_authorized':False},indent=2))
    if handle:
        print('Attached to existing flow completion event',pid,flush=True)
        try: assert kernel.WaitForSingleObject(handle,0xffffffff)==0
        finally: kernel.CloseHandle(handle)
    flow=json.loads((WORK/'flow_result.json').read_bytes())
    assert [s['stage'] for s in flow['stages']]==['compile','synthesize','pnr']
    assert all(s['exit_code']==0 for s in flow['stages'])
    results=[]
    for script in ['export_whole.py','generate_bitstream.py','verify_delivery.py']:
        print('Starting',script,flush=True)
        p=subprocess.run([sys.executable,str(HERE/script)],cwd=HERE)
        results.append({'script':script,'exit_code':p.returncode})
        (WORK/'finish_pipeline_result.json').write_text(json.dumps({'steps':results,'programming_performed':False},indent=2))
        assert p.returncode==0,'Stop at failed acceptance step: '+script
    print('Bitstream generated and delivery verified',flush=True)
if __name__=='__main__':main()
