"""Prepare only isolated PDS metadata; never copy or modify RTL/vendor IP."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
WORK = HERE / 'work'
REFERENCE = HERE.parent / 'sfp_100h_diag_mode0/baseline'
NEW = ('block_motion_detector.v', 'motion_stream_adapter.v', 'motion_register_bank.v')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf8')

def strip_runtime(raw):
    # Balanced nodes, including quoted parentheses and escaped quotes.
    spans = []
    for match in re.finditer(rb'\((_db_output|_output|_gci_state)\b|\(_file\s+"(?:compile|synthesize|device_map|place_route|report_timing|report_power|generate_netlist|generate_bitstream)/', raw):
        depth, quoted, escaped = 0, False, False
        for end in range(match.start(), len(raw)):
            byte = raw[end]
            if quoted and byte == 92 and not escaped:
                escaped = True
                continue
            if byte == 34 and not escaped:
                quoted = not quoted
            if not quoted:
                depth += (byte == 40) - (byte == 41)
                if depth == 0:
                    spans.append((match.start(), end + 1))
                    break
            escaped = False
        else:
            raise RuntimeError('Unbalanced baseline PDS')
    # Outer removal subsumes its child nodes.
    outer = []
    for start, end in sorted(spans):
        if not outer or start >= outer[-1][1]:
            outer.append((start, end))
    for start, end in reversed(outer):
        raw = raw[:start] + raw[end:]
    return raw

def registered(raw, require_files=True):
    paths = []
    for ref in re.findall(rb'\((?:_file|_ip_source_item)\s+"([^"]+)"', raw):
        name = ref.decode('gbk').replace('\\', '/')
        path = (WORK / name).resolve()
        if HERE not in path.parents or not name.startswith(('../source/', '../ipcore/')):
            raise RuntimeError('External/unexpected PDS input: ' + name)
        if require_files and not path.is_file():
            raise FileNotFoundError(path)
        paths.append(path)
    if not paths:
        raise RuntimeError('No registered inputs')
    return paths

def prepare(check=False):
    manifest = json.loads((HERE / 'baseline_manifest.json').read_text())
    expected = manifest['files']['baseline_project.pds']
    if sha(HERE / 'baseline_project.pds') != expected:
        raise RuntimeError('Immutable archived PDS changed')
    # IP copies must still equal the extraction manifest, including file inventory.
    ip_expected = {n.replace('\\', '/'): h for n, h in manifest['files'].items()
                   if n.replace('\\', '/').startswith('ipcore/')}
    ip_actual = {p.relative_to(HERE).as_posix(): sha(p)
                 for p in (HERE / 'ipcore').rglob('*') if p.is_file()}
    if not ip_expected or ip_actual != ip_expected:
        raise RuntimeError('Stage IP differs from immutable baseline manifest')
    for name, digest in manifest['files'].items():
        name = name.replace('\\', '/')
        if name.startswith('source/constraints/') and name.endswith('.fdc'):
            if sha(HERE / name) != digest:
                raise RuntimeError('Baseline constraint changed; review integration constraints: ' + name)
    raw = strip_runtime((HERE / 'baseline_project.pds').read_bytes())
    modules = list(NEW)
    if (HERE / 'source/motion/motion_result_cdc.v').is_file():
        modules.append('motion_result_cdc.v')
    insert = b'\n'.join(b'                (_file "../source/motion/' + n.encode() +
                        b'"\n                    (_format verilog)\n'
                        b'                    (_timespec "2026-10-03T00:00:00")\n                )'
                        for n in modules) + b'\n'
    pos = raw.index(b'                (_file ')
    raw = raw[:pos] + insert + raw[pos:]
    registered(raw, require_files=check)
    provenance = json.loads((REFERENCE / 'provenance.json').read_text())
    for name, key in [('top_pnr.adf', 'route_sha256'), ('top_prr.prt', 'pin_sha256')]:
        if sha(REFERENCE / name) != provenance[key]:
            raise RuntimeError('192245 final baseline hash mismatch: ' + name)
    if check:
        if (WORK / 'project.pds').read_bytes() != raw:
            raise RuntimeError('Prepared PDS differs from regenerated baseline')
        print('PASS PDS regeneration, registered paths, immutable IP and final baseline hashes')
        return
    if any((WORK / n).exists() for n in
           ('compile', 'synthesize', 'device_map', 'place_route')) or (
           (WORK / 'flow.pds').exists() and (WORK / 'flow.pds').read_bytes() != raw):
        raise RuntimeError('Existing runtime work; preparation will not overwrite it')
    WORK.mkdir(exist_ok=True)
    (WORK / 'project.pds').write_bytes(raw)
    (WORK / 'flow.pds').write_bytes(raw)
    baseline = HERE / 'baseline'
    baseline.mkdir(exist_ok=True)
    for name in ('top_pnr.adf', 'top_prr.prt', 'provenance.json',
                 'top_timing_summary_after_hold_fix.txt'):
        shutil.copy2(REFERENCE / name, baseline / name)
    save(HERE / 'preparation.json', {
        'project_sha256': sha(WORK / 'project.pds'), 'baseline_project_sha256': expected,
        'registered_references': len(registered(raw, False)), 'modules': modules,
        'ipcore_sha256': ip_actual, 'baseline_provenance': provenance,
        'baseline_files': {p.name: sha(p) for p in baseline.iterdir() if p.is_file()}})
    print('Prepared immutable work/project.pds; no vendor tools launched. Run --check after RTL is ready.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    prepare(parser.parse_args().check)
