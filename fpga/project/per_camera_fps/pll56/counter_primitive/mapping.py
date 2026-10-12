"""Fail-closed evidence for all four independently clocked source-drop counters."""
from pathlib import Path
import hashlib
import re

def verify_counter_mapping(netlist, controlsets):
    raw = Path(netlist).read_bytes()
    modules = [m.group() for m in re.finditer(rb'\nmodule [\s\S]+?\nendmodule', raw)
        if re.match(rb'\nmodule pll56_source_drop_counter(?:_unq\d+)?\s', m.group())]
    cells = [c.group() for m in modules for c in re.finditer(rb'\n    GTP_DFF[^;]+;', m)]
    errors = []
    if len(modules) != 4 or len(cells) != 128:
        errors.append('Require 4 counter modules / 128 FFs, got %d / %d' % (len(modules), len(cells)))
    for m in modules:
        local = list(re.finditer(rb'\n    GTP_DFF[^;]+;', m))
        if len(local) != 32:
            errors.append('Counter specialization missing 32 FFs')
    for cell in cells:
        if re.search(rb'\.CE\s*\(', cell):
            errors.append('Counter CE pin remains')
        if not re.match(rb'\n    GTP_DFF_C\s', cell):
            errors.append('Unexpected counter primitive')
        if not all(re.search(rb'\.'+port+rb'\s*\(', cell) for port in (b'Q',b'D',b'CLK',b'C')):
            errors.append('Missing primitive port')
    cs = Path(controlsets).read_bytes()
    dynamic = [line.decode('ascii','replace') for line in cs.splitlines()
               if b'u_src_drop' in line and b'CE(' in line]
    aliases = []
    cdc_modules = [m.group() for m in re.finditer(rb'\nmodule [\s\S]+?\nendmodule', raw)
        if re.match(rb'\nmodule ov5640_cdc(?:_unq\d+)?\s', m.group())]
    for line in dynamic:
        if not re.search(r'CE\([^)]*u_src_drop\.frame\)\s*:\s*97$', line):
            errors.append('Counter dynamic CE still in actual controlsets report')
            continue
        prefix = re.search(r'CE\((.*?)\.ov5640\.ov5640_cdc\.u_src_drop\.frame\)', line)
        if not prefix:
            errors.append('Unresolved frame alias hierarchy')
            continue
        camera = prefix.group(1).encode()
        matched = [m for m in cdc_modules if b'\\'+camera+b'/ov5640/' in m.split(b');',1)[0]
                   and re.search(rb'\.frame\s*\(N14\)', m)]
        if len(matched) != 1:
            errors.append('Frame alias must resolve to one CDC module')
            continue
        endpoints = [c.group() for c in re.finditer(rb'\n    GTP_DFF[^;]+;', matched[0])
                     if re.search(rb'\.CE\s*\(N14\)',c.group())]
        names = [re.search(rb'\.Q\s*\(([^)]+)',c).group(1).decode('ascii') for c in endpoints]
        families = {name: sum(q.split('[')[0] == name for q in names)
                    for name in ('src_seq','src_snapshot','src_toggle')}
        if len(endpoints) != 97 or families != dict(src_seq=32,src_snapshot=64,src_toggle=1):
            errors.append('Frame alias endpoints differ from proven non-counter CDC state')
            continue
        aliases.append(dict(report_row=line, resolved_ce='N14', endpoint_families=families,
                            endpoints=names))
    return dict(status='FAIL' if errors else 'PASS', errors=errors, counter_modules=len(modules),
        counter_register_cells=len(cells), netlist_sha256=hashlib.sha256(raw).hexdigest(),
        controlsets_sha256=hashlib.sha256(cs).hexdigest(), dynamic_controlsets=dynamic,
        verified_non_counter_frame_aliases=aliases,
        cells=[c.decode('ascii','replace') for c in cells])
