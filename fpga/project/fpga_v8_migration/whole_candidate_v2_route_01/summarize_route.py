"""Read completed isolated reports, preserving exact XML evidence and all table rows."""
from pathlib import Path
import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / 'evidence'
V2 = HERE.parent / 'whole_candidate_v2'

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

def main():
    receipt = json.loads((HERE / 'pnr_result.json').read_bytes())
    assert receipt['exit_code'] == 0, 'Failed PnR: retain all artifacts, no retry'
    assert receipt['protected_unchanged'] and receipt['local_sources_unchanged']
    EVIDENCE.mkdir(exist_ok=True)
    report = {'receipt': receipt, 'stage_reports': {}, 'warnings': {}, 'timing_signoff': False,
              'all_endpoint_paths_exported': False, 'hardware_acceptance': False}
    for stage, dbname in [('synthesize', 'snr.db'), ('place_route', 'prr.db'), ('report_timing', 'rtr.db')]:
        db = HERE / stage / dbname
        if db.is_file():
            report['stage_reports'][stage] = {'path': str(db), 'sha256': sha(db), 'tables': extract(db, stage)}
    log = (HERE / 'pnr_shell.log').read_bytes().decode('ascii', 'backslashreplace')
    warnings = [s for s in log.splitlines() if s.startswith(('W:', 'C: STA-'))]
    (EVIDENCE / 'warnings.txt').write_text('\n'.join(warnings) + '\n', encoding='ascii')
    report['warnings'] = {'count': len(warnings), 'codes': dict(collections.Counter(
        re.match(r'^[WC]:\s+([^: ]+)', s)[1] if re.match(r'^[WC]:\s+([^: ]+)', s) else 'uncoded' for s in warnings)),
        'ignored_io_delay_lines': [s for s in warnings if 'delay' in s.lower() and ('input' in s.lower() or 'output' in s.lower())],
        'endpoint_eligibility_lines': [s for s in warnings if 'eligible.addr_end_1' in s],
        'blackbox_lines': [s for s in warnings if 'blackbox' in s.lower() or 'black box' in s.lower()]}
    report['actual_flow_completions'] = receipt['completion_lines']
    report['selected_top_evidence'] = [s for s in log.splitlines() if 'set as top module' in s]
    report['six_source_fdc_hashes'] = {p.name: sha(p) for p in sorted((HERE / 'inputs/source/constraints').glob('*.fdc'))}
    report['registered_sources_after'] = json.loads((HERE / 'registered_sources_after.json').read_bytes())
    report['original_synthesis_comparison'] = json.loads((V2 / 'compile_01/attempt_01/evidence/check_timing_exact.json').read_bytes())
    base = json.loads((HERE / 'baseline_reference.json').read_bytes())
    actual = report['stage_reports'].get('place_route', {}).get('tables', {}).get('pnr_io_report', {})
    old = ET.fromstring(base['baseline_resources_and_pins']['pnr_io_report'])
    old_pins = {r.find('data').text: [d.text or '' for d in r.findall('data')] for r in old.findall('row')}
    new_pins = {r['data'][0]: r['data'] for r in actual.get('rows', [])}
    report['pins'] = {'old_count': len(old_pins), 'new_count': len(new_pins),
                      'all_electrical_attributes_identical': old_pins == new_pins,
                      'differences': {k: {'old': old_pins.get(k), 'new': new_pins.get(k)}
                                      for k in sorted(set(old_pins) | set(new_pins)) if old_pins.get(k) != new_pins.get(k)},
                      'hsst_physical_database_audit_pending': True}
    write('route_summary.json', report)
    print('Completed-report extraction saved. Flow:', report['actual_flow_completions'])
    print('PRR pad comparison:', report['pins'])
    for stage, data in report['stage_reports'].items():
        print(stage, list(data['tables']))

if __name__ == '__main__':
    main()
