"""Validate official functional-netlist export against the proven epoch10 DB."""
import json
from native_query08 import BASE, run, digest

if __name__ == '__main__':
    source = BASE / 'fixed_06/synthesis_epoch10'
    db = source / 'synthesize/v7_sdt_top_syn.adf'
    proof = json.loads((source / 'topology_validated.json').read_bytes())
    assert proof['pairs'] == 1280 and digest(db) == proof['synth_db_sha256']
    text = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
            'gen_netlist -force_to_run -func_sim_only -sdf_annotate FALSE -input_db_file {'
            + db.as_posix() + '}\n')
    out, code = run('syn_netlist24', text, [db])
    files = [
        {'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
        for p in out.rglob('*') if p.is_file() and p.suffix.lower() in ('.v', '.vm', '.vhd', '.sdc', '.scf', '.lcf')
    ]
    (out / 'netlist_inventory.json').write_text(json.dumps({
        'exit_code': code, 'files': files, 'source_db_unchanged': digest(db) == proof['synth_db_sha256'],
        'constraint_loading_proven': False, 'bit_permitted': False,
    }, indent=2))
    print(json.dumps(files, indent=2), flush=True)
