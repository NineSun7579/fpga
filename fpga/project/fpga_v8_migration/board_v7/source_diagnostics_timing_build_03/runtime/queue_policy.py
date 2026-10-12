"""Serial tools and prior-controller lifetimes, excluding self-dependent observers."""
import re
from pathlib import Path

def classify_processes(current,own_pid):
    busy=[];observers=[];bypid={p['ProcessId']:p for p in current};ancestors=set()
    parent=bypid.get(own_pid,{}).get('ParentProcessId')
    while parent in bypid and parent not in ancestors:
        ancestors.add(parent);parent=bypid[parent].get('ParentProcessId')
    for p in current:
        name=p['Name'].lower();command=p.get('CommandLine') or '';pid=p['ProcessId']
        if pid==own_pid or p.get('ParentProcessId')==own_pid:continue
        if name in {'pds.exe','pds_shell.exe','ta.exe'}:busy.append(p);continue
        if pid in ancestors:observers.append(p);continue
        if re.search(r'(?i)Wait-Process\b[^;\r\n]*\b'+str(own_pid)+r'\b',command):observers.append(p);continue
        normalized=command.replace('\\','/').lower()
        scripts=set(re.findall(r'([a-z0-9_]+\.py)\b',normalized))
        executor=name in {'python.exe','pythonw.exe','powershell.exe','pwsh.exe','cmd.exe'}
        # Actual launchers/full controller lifetimes including map02, build01,
        # build02 and physical-probe finishers, not merely tool child processes.
        full_prior=('board_v7/' in normalized and bool(scripts) and 'source_diagnostics_timing_build_03/' not in normalized)
        named=bool(scripts & {'controller02.py','controller03.py','physical_flow.py','run_official_attempt03.py',
            'run_clock_epoch25.py','probe_official_mapping.py','audit_comparison.py','run_map_audit14.py',
            'run_exact11.py','resume_exact11.py','recover_compile_attempt.py','run_pds.py','finalize_exact11.py'})
        if executor and (full_prior or named):busy.append(p)
    return busy,observers
