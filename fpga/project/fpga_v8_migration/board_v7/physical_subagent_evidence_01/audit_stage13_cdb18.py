"""Read-only audit of saved stage13 mapped CDB; never launches PDS."""
import collections
import hashlib
import json
from pathlib import Path
from prove_cdb11 import parse_cdb, field

BASE = Path(__file__).resolve().parent

def main():
    dump = BASE / 'fixed_06/map_audit14/actual/synthesis_export/synthesis_dump.txt'
    cdb = parse_cdb(dump)
    records = [e for e in cdb[1:] if isinstance(e, list)]
    budgets = [e for e in records if e[0] == 'MMD']
    result = {
        'dump': str(dump),
        'sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
        'node_counts': dict(collections.Counter(e[0] for e in records)),
        'maxdelay_records': budgets,
        'budget_15238_datapath_only_count': sum(
            field(e, 'DELAY') == '15238' and field(e, 'DATAPATH_ONLY') == '1'
            for e in budgets),
        'budget_loading_proven': False,
    }
    # Presence alone cannot prove object coverage; absence decisively fails loading.
    output = BASE / 'fixed_06/map_audit14/stage13_cdb18_audit.json'
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
