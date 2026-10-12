from pathlib import Path
import hashlib, json, xml.etree.ElementTree as ET
from preflight import HERE as BUILD_ROOT
HERE=BUILD_ROOT/'evidence/runtime'
EVIDENCE=HERE/'evidence'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def write(name, obj):
    (EVIDENCE / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def row(row):
    return {'data': [d.text or '' for d in row.findall('data')],
            'attributes': row.attrib,
            'children': [globals()['row'](r) for r in row.findall('row')]}

def extract(path, label):
    output = {}
    # End-event streaming avoids loading potentially multi-GB detailed-path DBs.
    depth = 0
    for event, elem in ET.iterparse(path, events=['start', 'end']):
        if event == 'start':
            depth += 1
            continue
        if elem.tag == 'table':
            ident = elem.attrib.get('id', '')
            if any(k in ident for k in ['summary', 'check_timing', 'clock', 'setup', 'hold', 'recovery', 'removal',
                                        'pulse', 'fmax', 'constraint', 'resource', 'io_report', 'pinout', 'messages']):
                filename = label + '_' + ident + '.xml'
                (EVIDENCE / filename).write_bytes(ET.tostring(elem, encoding='utf-8'))
                output[ident] = {'attributes': elem.attrib,
                                 'headers': [d.text or '' for d in elem.findall('column_headers/data')],
                                 'rows': [row(r) for r in elem.findall('row')],
                                 'exact_xml': filename}
            elem.clear()
        # Very large detailed path blocks are not summaries. Clear at top-level completion.
        if depth == 2:
            elem.clear()
        depth -= 1
    return output

