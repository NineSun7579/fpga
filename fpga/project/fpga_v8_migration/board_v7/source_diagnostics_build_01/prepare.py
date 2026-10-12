"""Isolated byte-preserving V7 diagnostic physical attempt; no programming."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess

HERE = Path(__file__).resolve().parent
M = HERE.parents[1]
BASE = M / 'whole_candidate_v7_route_01'
CAND = HERE.parent / 'source_diagnostics_top_candidate'
PDS = Path(r'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

def idle(label):
    cmd = ['powershell.exe', '-NoProfile', '-Command', 'ConvertTo-Json -InputObject @(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName) -Compress']
    items = json.loads(subprocess.run(cmd, capture_output=True, check=True).stdout)
    save('processes_' + label + '.json', items)
    assert not items, 'PDS single-instance gate'

def inventory():
    files = [p for folder in ['inputs', 'rtl'] for p in (HERE / folder).rglob('*') if p.is_file()]
    return {str(p.relative_to(HERE)): sha(p) for p in files}

def protected():
    files = [p for folder in ['inputs', 'rtl', 'evidence'] for p in (BASE / folder).rglob('*') if p.is_file()]
    files += [BASE / 'project.pds', BASE / 'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf']
    files += [p for p in CAND.iterdir() if p.is_file()]
    files += [M / 'board_v7/source_frame_diagnostics_candidate/v7_sfd_candidate.v']
    files += [p for p in (M.parent / 'ipcore').rglob('*') if p.is_file()]
    return {str(p): sha(p) for p in files}

def main():
    assert not (HERE / 'project.pds').exists(), 'Never overwrite attempt'
    idle('before_prepare')
    # Verify the actual simulation input hashes before copying hardware sources.
    hashes = json.loads((CAND / 'source_hashes.json').read_bytes())
    assert all(sha(Path(p)) == h for p, h in hashes.items())
    baseline = protected()
    save('protected_before.json', baseline)
    warnings = json.loads((CAND / 'warnings.json').read_bytes())
    assert warnings['elaboration.log']['count'] == 600
    operations = json.loads((CAND / 'generation_operations.json').read_bytes())
    save('connection_review.json', {
        'elaboration_warnings': warnings, 'generation_operations': operations,
        'reviewed_changes': ['AW/W simultaneous issue retaining independent handshakes',
                             'retired M00 BID/BRESP/BUSER/BVALID zero tieoff; read path retained',
                             'S00 AWLEN/ARLEN explicit 4-bit zero extension'],
        'open_risks': ['600 elaboration warnings not waived', 'bridge 4-bit to 8-bit LEN warning retained',
                       'digital tests do not prove DDR/PCIe/physical reset or CDC timing']})
    for folder in ['inputs', 'rtl']:
        shutil.copytree(BASE / folder, HERE / folder)
    project = (BASE / 'project.pds').read_bytes()
    substitutions = {
        'rtl/fpga_v8_cooperative_top_v2_rfg01.v': 'v7_sdt_top.v',
        'rtl/parent_tc04_c40cee500c37.v': 'v7_sdt_camera.v',
        'rtl/ov5640_tc03_binding.v': 'v7_sdt_binding.v'}
    for old, name in substitutions.items():
        assert project.count(old.encode()) == 1
        project = project.replace(old.encode(), ('rtl/' + name).encode())
        shutil.copyfile(CAND / name, HERE / 'rtl' / name)
    for name, src in [('v7_sdt_bus.v', CAND / 'v7_sdt_bus.v'),
                      ('v7_sfd_candidate.v', M / 'board_v7/source_frame_diagnostics_candidate/v7_sfd_candidate.v')]:
        shutil.copyfile(src, HERE / 'rtl' / name)
    anchor = b'(_file "rtl/v7_sdt_top.v"'
    assert project.count(anchor) == 1
    project = project.replace(anchor, b'(_file "rtl/v7_sdt_bus.v"\n                    (_format verilog)\n                    (_timespec "2026-10-06T10:32:26")\n                )\n                (_file "rtl/v7_sfd_candidate.v"\n                    (_format verilog)\n                    (_timespec "2026-10-06T10:32:26")\n                )\n                ' + anchor)
    # Replace only the project top identity, not any frozen RTL contents.
    project = project.replace(b'fpga_v8_cooperative_top_v2_rfg01', b'v7_sdt_top')
    project = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project)
    (HERE / 'project.pds').write_bytes(project)
    save('project_initial.json', {'sha256': sha(HERE / 'project.pds')})
    modules = {}
    for raw in re.findall(rb'\(_file "([^"]+\.v)"', project):
        p = HERE / raw.decode('ascii')
        clean = re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', p.read_bytes(), flags=re.S)
        for name in re.findall(rb'\bmodule\s+(\w+)', clean):
            modules.setdefault(name.decode(), []).append(str(p.relative_to(HERE)))
    conflicts = {k:v for k,v in modules.items() if len(v)>1}
    assert not conflicts, conflicts
    save('module_scan.json', {'registered_modules':len(modules), 'conflicts':conflicts})
    save('inputs_before.json', inventory())
    assert baseline == protected(), 'Protected inputs drift'
    save('preparation.json', {'passed':True, 'top':'v7_sdt_top', 'frozen_inputs':694,
                             'original_constraints_unchanged':True, 'new_cdc_constraints_pending':True,
                             'programming_performed':False})
    print('Prepared isolated project; frozen inputs intact; CDC constraint gate before PNR', flush=True)

if __name__ == '__main__':
    main()
