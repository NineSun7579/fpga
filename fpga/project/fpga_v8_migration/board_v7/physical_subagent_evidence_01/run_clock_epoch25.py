"""Fresh synthesis experiment: clock budgets without mailbox pin tagging.

Never maps or routes. Exact object scope and downstream coverage remain gates.
"""
import json
import re
import shutil
import traceback
from pathlib import Path
import run_synthesis_epoch10 as epoch
from native_query08 import BASE, PDS, idle
from prepare_query_epoch08 import main as prepare
from generate_exact11 import coll
from prove_cdb11 import parse_cdb, field

OUT = BASE / 'fixed_06/clock_epoch25'

def main():
    idle()
    guard = json.loads((BASE.parent / 'source_diagnostics_route_01/build01_guard.json').read_bytes())
    assert len(guard) == 1022
    assert all(epoch.sha(Path(p)) == h for p, h in guard.items())
    off = json.loads((BASE / 'fixed_06/physical_exact_11/coverageproof_offline.json').read_bytes())
    assert len(off['retained_clock_pairs']) == 364
    prepare(OUT, BASE / 'synthesis_epoch10_tail.fdc')
    shutil.move(str(OUT / 'compile'), str(OUT / 'copied_compile_archive'))
    project = OUT / 'query_epoch08.pds'
    project.write_bytes(re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project.read_bytes()))
    clock = OUT / 'clock.fdc'
    base = b'\n'.join(line for line in clock.read_bytes().splitlines()
                       if not line.strip().startswith(b'set_clock_groups ')) + b'\n'
    lines = ['# Experimental clock-scoped budgets: exact coverage is pending.']
    for a, b in off['retained_clock_pairs']:
        lines.append(f'set_false_path -from [get_clocks {{{a}}}] -to [get_clocks {{{b}}}]')
    for camera in off['cameras']:
        i = camera['camera']
        pins = camera['compile_complement']
        assert pins and not any('/mailbox[' in pin for pin in pins)
        lines.append('set_false_path -from ' + coll(pins) + ' -to [get_clocks {ddrphy_sysclk}]')
        clocks = f'-from [get_clocks {{cmos{i+1}_pclk}}] -to [get_clocks {{ddrphy_sysclk}}]'
        lines.append('set_max_delay -datapath_only 15.238 ' + clocks)
        lines.append('set_false_path -hold ' + clocks)
    clock.write_bytes(base + '\n'.join(lines).encode('ascii') + b'\n')
    inputs = {str(p): epoch.sha(p) for p in OUT.glob('*.fdc')}
    (OUT / 'intent.json').write_text(json.dumps({
        'expected_pairs': 1280, 'retained_clockpairs': 364,
        'compile_complements': [len(c['compile_complement']) for c in off['cameras']],
        'coverage_pending': True, 'map_permitted': False, 'bit_permitted': False,
        'fdc_hashes': inputs,
    }, indent=2))
    epoch.OUT = OUT
    epoch.run('synthesize', [PDS, '-project', str(project), '-run', 'synthesize', '-work_dir', str(OUT)], OUT,
              ['Process "Compile" done.', 'Process "Synthesize" done.', 'has been successfully synthesized'])
    db = OUT / 'synthesize/v7_sdt_top_syn.adf'
    before = epoch.sha(db)
    actual = OUT / 'actual'
    (actual / 'synthesis_export').mkdir(parents=True)
    (actual / 'analysis').mkdir()
    dump = actual / 'synthesis_export/synthesis_dump.txt'
    script = actual / 'export.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n.switch_db -input {'
                      + db.as_posix() + '} -output {' + dump.as_posix() + '}\n', encoding='ascii')
    epoch.run('export_syn', [PDS, '-file', str(script), '-work_dir', str(actual), '-project_name', 'clock_epoch25_export'], actual)
    origin = BASE.parent / 'source_diagnostics_route_01/actual'
    for name in ['parse_objects.py', 'resolve_manifest.py', 'derive_exact_complement.py', 'classify_paths.py', 'B_one_pair.sdc']:
        shutil.copy2(origin / name, actual / 'analysis' / name)
    for name in ['parse_objects', 'resolve_manifest', 'derive_exact_complement', 'classify_paths']:
        epoch.run(name, ['python', str(actual / 'analysis' / (name + '.py'))], actual)
    manifest = json.loads((actual / 'analysis/manifest.json').read_bytes())
    exact = json.loads((actual / 'analysis/exact_complement.json').read_bytes())
    budgets = [e for e in parse_cdb(dump)[1:] if isinstance(e, list) and e[0] == 'MMD']
    pairs = sum(len(c['bundle_pairs']) for c in exact['cameras'])
    result = {'pairs': pairs, 'expected_pairs': 1280,
              'complements': [len(c['complement_launch_pins']) for c in exact['cameras']],
              'manifest_errors': manifest['errors'], 'complement_errors': exact['errors'],
              'maxdelay_records': budgets,
              'four_budget_records_present': len(budgets) == 4 and all(field(e, 'DELAY') == '15238' and field(e, 'DATAPATH_ONLY') == '1' for e in budgets),
              'synth_db_sha256': before, 'inputs_unchanged': all(epoch.sha(Path(p)) == h for p, h in inputs.items()),
              'protected_mismatches': [p for p, h in guard.items() if epoch.sha(Path(p)) != h],
              'coverage_pending': True, 'map_permitted': False, 'bit_permitted': False}
    (OUT / 'topology_result.json').write_text(json.dumps(result, indent=2))
    assert epoch.sha(db) == before
    print(json.dumps({k: v for k, v in result.items() if k != 'maxdelay_records'}, indent=2), flush=True)
    assert pairs == 1280 and not manifest['errors'] and not exact['errors'], 'Topology gate failed; do not map'
    assert result['four_budget_records_present'] and result['inputs_unchanged'] and not result['protected_mismatches']

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        if OUT.exists():
            (OUT / 'failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        raise
