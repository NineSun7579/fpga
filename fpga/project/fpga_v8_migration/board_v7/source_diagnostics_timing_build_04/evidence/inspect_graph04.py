from pathlib import Path
import json
h=Path(__file__).resolve().parent.parent
g=json.loads((h/'evidence/runtime/compile/analysis/graph.json').read_bytes())
for c in ['source_diagnostics/cameras[0].source/cr','source_diagnostics/cameras[0].source/cr_ff0']:
    print(c,json.dumps(g['primitives'][c],indent=2))
    print({p:n for p,n in g['pin_net'].items() if p.startswith(c+'/')})
proof=json.loads((h/'evidence/runtime/compile_endpoint_details.json').read_bytes())
row=proof['failed_checks'][0]
for n in row['clock_actual_nets_traversed']:
    print('CLOCK',n,[a for a in g['net_aliases'].get(n,[]) if 'ddrphy_sysclk' in a or '/' not in a.strip('/')][:20])
print('ddr aliases',[(n,[x for x in a if 'ddrphy_sysclk' in x]) for n,a in g['net_aliases'].items() if any('ddrphy_sysclk' in x for x in a)])
