import json
from pathlib import Path
h=Path(__file__).resolve().parent.parent
g=json.loads((h/'evidence/runtime/actual/analysis/graph.json').read_bytes())
c=next(c for c in g['primitives'] if 'cr_ff0' in c)
print(c)
n=g['pin_net'][c+'/D'];print(n,g['net_aliases'].get(n))
for pin in g['netpins'][n]:
    cell,p=pin.rsplit('/',1);r=g['primitives'][cell]
    if r['ports'][p]['direction']=='OUTPUT':print(pin,json.dumps(r,indent=2))
print('RESET ALIASES',[(n,[a for a in aa if any(s in a for s in ['cam_reset','diag_reset','reset_any','source_diagnostics/rst'])]) for n,aa in g['net_aliases'].items() if any(any(s in a for s in ['cam_reset','diag_reset','reset_any','source_diagnostics/rst']) for a in aa)])
def cone(n,depth=0):
    print(' '*depth,n,g['net_aliases'].get(n,[])[:15])
    if depth>5:return
    for pin in g['netpins'][n]:
        cell,p=pin.rsplit('/',1);r=g['primitives'][cell]
        if r['ports'][p]['direction']=='OUTPUT':
            print(' '*depth,cell,r['type'],r['parameters'],r['default_parameters'])
            if 'DFF' not in r['type']:
                for port,v in r['ports'].items():
                    if v['direction']=='INPUT' and cell+'/'+port in g['pin_net']:cone(g['pin_net'][cell+'/'+port],depth+1)
cone(g['pin_net'][c+'/P'])
