"""Capture actual counts, never substitute expected counts for measured evidence."""
from prepare_offline import HERE,B04,sha,save
import json,collections,re
a=HERE/'offline_fresh_synthesis/analysis'
m=json.loads((a/'manifest.json').read_bytes()); rows=[]
for camera in range(4):
    resolved=[x for x in m['resolved'] if x['camera']==camera]
    regs=[x for x in resolved if x['mapping']['kind']=='register']
    pairs=collections.Counter((x['mapping']['launch_CLK'],x['mapping']['capture_D']) for x in regs)
    rows.append({'camera':camera,'logical_bits':len(resolved),'register_resolution_rows':len(regs),
                 'unique_actual_pairs':len(pairs),'constants':len(resolved)-len(regs),
                 'duplicates':[{'pair':list(p),'multiplicity':n} for p,n in pairs.items() if n>1]})
clock=B04/'inputs/source/constraints/clock.fdc';raw=clock.read_text(encoding='ascii')
clocks=set();groups=[]
for line in raw.splitlines():
    line=line.lstrip()
    if line.startswith(('create_clock ','create_generated_clock ')):
        clocks.add(re.search(r'-name\s+\{([^}]+)\}',line)[1])
    if line.startswith('set_clock_groups '):groups+=re.findall(r'-group\s+\[get_clocks\s+\{?(\w+)\}?\]',line)
u={(x,y) for x in clocks for y in clocks if x!=y and (x in groups or y in groups)}
carved={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
save('actual_offline_inventory.json',{'manifest_sha256':sha(a/'manifest.json'),'graph_sha256':sha(a/'graph.json'),
     'compile_graph_sha256':sha(B04/'evidence/runtime/compile/analysis/graph.json'),
     'clock_sha256':sha(clock),'resolved_logical_bits':len(m['resolved']),'resolve_errors':m['errors'],'cameras':rows,
     'register_resolution_rows':sum(r['register_resolution_rows'] for r in rows),
     'unique_actual_pairs':sum(r['unique_actual_pairs'] for r in rows),'required_unique_actual_pairs':1320,
     'mailbox1320_gate':False,'clocks':sorted(clocks),'U_declared':len(u),'U_minus_B':len(u-carved),
     'carved':sorted(carved),'ddr_mhz':25*84/16,'required_budget_ns':15.238,
     'derivation_completed':False,'constraints_qualified':False,'physical_signoff':False})
