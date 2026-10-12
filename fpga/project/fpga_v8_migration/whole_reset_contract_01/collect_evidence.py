"""Read-only byte audit; writes solely beside this script. Never invokes hardware."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
CAND = ROOT / 'fpga_v8_migration/whole_candidate_v2_route_01'
project = CAND / 'project.pds'
registered = re.findall(rb'\(_file "([^"]+)"', project.read_bytes())
files = [project]
files += [CAND / p.decode('ascii') for p in registered if p.startswith((b'rtl/', b'inputs/source/'))]
files += list((CAND / 'inputs/ipcore').rglob('*.v'))
files += list((CAND / 'inputs/ipcore').rglob('*.vp'))
for directory in ['capture_host', 'cooperative_host', 'epoch_allocator', 'pcie_retirement_contract', 'pcie_h2f_transport_contract', 'driver_ownership_audit']:
    files += [p for p in (ROOT / 'fpga_v8_migration' / directory).rglob('*') if p.is_file() and p.suffix in {'.py', '.hpp', '.h', '.c', '.md', '.json', '.cpp', '.sv', '.txt'} and 'artifacts' not in p.parts]
files += [p for p in (ROOT / 'tools').rglob('*') if p.is_file() and p.suffix in {'.py', '.sh', '.md', '.cpp', '.c'}]
manifest = []
excerpts = []
pattern = re.compile(rb'reset|rst|epoch|generation|quies|ArmRequest|UnknownResponse|Uncertain|PIPE_|WB_|SID|write_hold|write_active|read_active|buffer|core_clk|axi_clk|config_ready|engine_idle|outstanding|download|program|PERST|FLR', re.I)
for path in sorted(set(files)):
    if not path.exists():
        continue
    data = path.read_bytes()
    relative = path.relative_to(ROOT).as_posix()
    manifest.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    matched = [] if path.suffix == '.vp' else [f'{i}: {line.decode("ascii", "backslashreplace")}' for i, line in enumerate(data.splitlines(), 1) if pattern.search(line)]
    if matched:
        excerpts.append('\nFILE ' + relative + '\n' + '\n'.join(matched))
    if path.parent == CAND / 'rtl' or path.name in {'axi_dma_write.v', 'ov5640_cdc.v', 'ov5640_ddr_w.v', 'hsst_rst_cross_sync_v1_0.v', 'hsst_rst_sync_v1_0.v'}:
        dest = OUT / 'source_ascii' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('\n'.join(f'{i}: {line.decode("ascii", "backslashreplace")}' for i, line in enumerate(data.splitlines(), 1)) + '\n', encoding='ascii')
(OUT / 'source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='ascii')
(OUT / 'reset_excerpts.txt').write_text('\n'.join(excerpts), encoding='ascii')
print(json.dumps({'files': len(manifest), 'output': str(OUT), 'encoding': 'raw bytes -> ASCII backslashreplace'}))
