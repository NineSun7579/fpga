"""Read actual PLACE annotations and implemented IO cell parameters, not LOC intent."""
import hashlib
import json
from pathlib import Path
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def expected(fdc):
    ports = {}
    for port, attr, value in re.findall(rb'^define_attribute\s+\{p:([^}]+)\}\s+\{(PAP_IO_\w+)\}\s+\{([^}]+)\}', fdc.read_bytes(), re.M):
        ports.setdefault(port.decode(), {})[attr.decode()] = value.decode()
    for port, loc in {'sys_clk': 'P20', 'sfp0_tx_disable': 'H12', 'sfp0_los': 'E16', 'sfp1_tx_disable': 'F16'}.items():
        if ports.get(port, {}).get('PAP_IO_LOC') != loc:
            raise RuntimeError('Critical original pin expectation missing: ' + port)
    if len(ports) != 42 or any('PAP_IO_LOC' not in p or 'PAP_IO_STANDARD' not in p for p in ports.values()):
        raise RuntimeError('Expected complete 42 ordinary IO constraints')
    return ports


def audit_pcf(fdc, pcf):
    want = expected(fdc)
    actual = {name: dict(re.findall(r'(\w+)=([^\s]+)', attrs)) for name, attrs in
              re.findall(r'^def_port\s+\{([^}]+)\}\s+(.*)$', pcf.read_text(), re.M)}
    problems = []
    if set(actual) != set(want):
        problems.append('Physical PCF port coverage differs from source FDC')
    for name, attrs in want.items():
        for key, value in attrs.items():
            if key == 'PAP_IO_DIRECTION':
                continue
            # PDS resolves NONE plus later PULLUP=TRUE to the pull-up setting.
            if key == 'PAP_IO_NONE' and attrs.get('PAP_IO_PULLUP') == 'TRUE':
                continue
            key = key.removeprefix('PAP_IO_').replace('STANDARD', 'IOSTANDARD')
            if actual.get(name, {}).get(key) != value:
                problems.append(f'{name} {key}: expected {value}, got {actual.get(name, {}).get(key)}')
    if 'def_inst_site {u_hsst/U_GTP_HSST_WRAPPER/U_GTP_HSST/hsst} HSST_88_340' not in pcf.read_text():
        problems.append('HSST physical location missing')
    if problems:
        raise RuntimeError('Physical PCF blocked: ' + '; '.join(problems))
    return {'ports': actual, 'pcf_sha256': hashlib.sha256(pcf.read_bytes()).hexdigest()}


def audit_dump(fdc, dump, package_report):
    want = expected(fdc)
    text = dump.read_bytes().decode('gb18030')
    package = {}
    for line in package_report.read_text().splitlines():
        columns = line.split('|')
        if len(columns) >= 3:
            package[columns[1]] = {'pin': columns[0], 'bank': columns[2]}
    placements = {}
    for name, impl, device, x, y in re.findall(r'\(INSTANNOTATE \(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(\S+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)', text):
        value = {'impl': impl, 'device': device, 'x': int(x), 'y': int(y)}
        if name in placements and placements[name] != value:
            raise RuntimeError('Conflicting physical annotations: ' + name)
        placements[name] = value
    cells = {}
    for name, block in re.findall(r'^    \(CELL\s+(\S+)\s+(.*?)(?=^    \))', text, re.M | re.S):
        cells[name] = dict(re.findall(r'\(PARAMETER\s+(\w+)\s+\(DATATYPE STRING\)\s+\(STRING "?([^"()]+?)"?\)\)', block))
    instances = {}
    for name, cell, block in re.findall(r'^          \(INSTANCE\s+(\S+)\s+\(VIEWREF[^\n]*?\(CELLREF\s+(\S+)[^\n]*\n(.*?)(?=^          \))', text, re.M | re.S):
        instances[name] = {'cell': cell, 'attrs': dict(re.findall(r'\(ATTRIBUTE\s+(\w+)\s+\(STRING "?([^"()]+?)"?\)\)', block))}
    nets = {}
    for name, block in re.findall(r'^          \(NET\s+([^\n]+)\n(.*?)(?=^          \))', text, re.M | re.S):
        name = name.strip()
        indexed = re.fullmatch(r'\(INDEXED (\S+) (\d+)\)', name)
        if indexed:
            name = f'{indexed[1]}[{indexed[2]}]'
        nets[name.lstrip('\\')] = block
    actual, problems = {}, []
    connections = re.findall(r'^            \(CONNECT[^\n]*\n(.*?)(?=^            \))', text, re.M | re.S)
    implemented_io = {name for name, inst in instances.items()
                      if inst['cell'].startswith(('gopIBUF', 'gopOBUF')) and 'IOL' not in inst['cell']}
    covered_io = set()
    for port, attrs in want.items():
        # DevMap's IO primitive retains original port attributes. PLACE supplies
        # the actual package site; the resolved cell supplies electrical settings.
        candidates = [(name, inst) for name, inst in instances.items()
                      if inst['attrs'].get('PAP_IO_LOC') == attrs['PAP_IO_LOC']
                      and inst['cell'].startswith(('gopIBUF', 'gopOBUF'))
                      and 'IOL' not in inst['cell']]
        if not candidates:
            if port in ('key1', 'key2') and not any(f'(PORTREF {port})' in b for b in connections):
                actual[port] = [{'state': 'optimized_dangling', 'expected': attrs}]
                continue
            problems.append('No implemented IO primitive for ' + port)
            continue
        rows = []
        if len(candidates) != 1:
            problems.append('Ambiguous IO primitive: ' + port)
        for name, inst in candidates:
            covered_io.add(name)
            indexed_port = re.fullmatch(r'(\w+)\[(\d+)\]', port)
            portref = f'(PORTREF (INDEXED {indexed_port[1]} {indexed_port[2]}))' if indexed_port else f'(PORTREF {port})'
            if not any(portref in b and re.search(r'\(INSTREF\s+' + re.escape(name) + r'\s*\)', b) for b in connections):
                problems.append('External port does not connect to audited IO primitive: ' + port)
            place = placements.get(name, {})
            site = f"{place.get('device')}_{place.get('x')}_{place.get('y')}"
            pin = package.get(site, {})
            params = cells.get(inst['cell'], {})
            row = {'instance': name, 'site': site, **pin, 'cell': inst['cell'], 'parameters': params}
            rows.append(row)
            if pin.get('pin') != attrs['PAP_IO_LOC']:
                problems.append(f'{port} actual pin {pin.get("pin")} != {attrs["PAP_IO_LOC"]}')
            for key, param in (('PAP_IO_STANDARD', 'IOSTANDARD'), ('PAP_IO_VCCIO', 'VCCIO'), ('PAP_IO_DRIVE', 'DRV_CURR_VAL')):
                if key in attrs and params.get(param) != attrs[key]:
                    problems.append(f'{port} implemented {param} {params.get(param)} != {attrs[key]}')
            if 'PAP_IO_SLEW' in attrs and params.get('SLEW_MODE') != {'SLOW': 'S', 'FAST': 'F'}[attrs['PAP_IO_SLEW']]:
                problems.append('Implemented slew mismatch: ' + port)
            terminated = 'PULLUP' if attrs.get('PAP_IO_PULLUP') == 'TRUE' else 'NONE'
            if params.get('TERMINATED') != terminated:
                problems.append('Implemented termination mismatch: ' + port)
        actual[port] = rows
    if covered_io != implemented_io or len(covered_io) != 40:
        problems.append('Implemented IO coverage incomplete: ' + repr(sorted(implemented_io - covered_io)))
    hsst = r'\u_hsst/U_GTP_HSST_WRAPPER/U_GTP_HSST/hsst'
    place = placements.get(hsst, {})
    if (place.get('device'), place.get('x'), place.get('y')) != ('HSST', 88, 340):
        problems.append('Actual HSST site differs from HSST_88_340')
    dedicated = {}
    for port, pad in {**{f'sfp{s}_{direction}{pol}': f'PAD_{direction.upper()}_SD{pol.upper()}{s+2}'
                        for s in range(2) for direction in ('rx', 'tx') for pol in ('p', 'n')},
                      'sfp_refckp': 'PAD_REFCLKP_0', 'sfp_refckn': 'PAD_REFCLKN_0'}.items():
        block = nets.get(port, '')
        if f'(PORTREF {port})' not in block or not re.search(r'\(PORTREF\s+' + pad + r'\s+\(INSTREF\s+' + re.escape(hsst) + r'\s*\)', block):
            problems.append('Dedicated HSST pad connection mismatch: ' + port)
        dedicated[port] = {'pad': pad, 'site': place}
    return {'ports': actual, 'dedicated_hsst_ports': dedicated, 'placements_sha256': digest(placements),
            'placement_count': len(placements), 'physical_io_sha256': digest({'ports': actual, 'hsst': dedicated}),
            'dump_sha256': hashlib.sha256(dump.read_bytes()).hexdigest(), 'problems': problems}
