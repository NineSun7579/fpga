"""Read-only baseline evidence preparation; writes solely inside new route project."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1] / 'motion_100h/run_20261003_212303'

def hash_file(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    result = {'baseline': str(BASE), 'baseline_resources_and_pins': {}, 'baseline_sta': {}, 'reference_files': {}}
    for name in ['resource_proof.json', 'phy_audit.json', 'final_sta_proof.json', 'pin_audit.json']:
        p = BASE / name
        result['reference_files'][name] = {'sha256': hash_file(p), 'size': p.stat().st_size}
    for stage, path in [('baseline_resources_and_pins', BASE / 'routed/prr.db')]:
        root = ET.parse(path).getroot()
        for child in root:
            result[stage][child.attrib.get('id', child.tag)] = ET.tostring(child, encoding='unicode')
    result['baseline_sta'] = json.loads((BASE / 'final_sta_proof.json').read_bytes())
    result['baseline_motion_requirements'] = json.loads((BASE / 'resource_requirements.json').read_bytes())
    (HERE / 'baseline_reference.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    with (BASE / 'final_sta/report_timing/top.rtr').open('rb') as f:
        print(f.read(1900).decode('ascii', 'backslashreplace'))
    print('baseline_reference.json prepared without changes to baseline.')
    for key in ['pnr_resource_usage', 'pnr_clock_summary']:
        print(result['baseline_resources_and_pins'].get(key, '')[:1900])

if __name__ == '__main__':
    main()
