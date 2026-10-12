"""Compare complete replacement against independently signed command inventory."""
import re
import json
from contract import BOARD,SOURCE,CONTRACT,load,require,sha
def audit(raw,proof):
    proof=json.loads(json.dumps(proof))
    base=(SOURCE/'inputs/source/constraints/clock.fdc').read_bytes()
    prefix=b'\n'.join(l for l in base.splitlines() if not l.lstrip().startswith(b'set_clock_groups '))+b'\n'
    require(raw.startswith(prefix),'Original clock/uncertainty/multicycle changed')
    def commands(b):return [l.strip() for l in b.decode('ascii').splitlines() if l.strip() and not l.lstrip().startswith('#')]
    reference=BOARD/'build04_mailbox_clock_review01/diagnostic_constraint_DRAFT/clock.fdc'
    require(sha(reference)==CONTRACT['timing']['constraint_draft_sha256'],'Signed clock reference drift')
    require(commands(raw)==commands(reference.read_bytes()),'Exact cross-membership/maxdelay/hold/ACK command sets differ')
    signed=load(BOARD/'build04_mailbox_clock_review01/diagnostic_constraint_DRAFT/coverageproof.json')
    require(proof['U']==signed['U'] and proof['retained_clock_pairs']==signed['retained_clock_pairs'],'Exact U-B differs')
    for a,b in zip(proof['cameras'],signed['cameras']):
        for k in ['compile','synthesis','compile_mailbox','physical_pairs','complement','ack_first']:
            require(a[k]==b[k],'Fresh clock membership differs '+k)
        require(not set(a['complement']) & ({p[0] for p in a['physical_pairs']}|set(a['compile_mailbox'])),'Mailbox included in complement')
    text=prefix.decode('ascii');clean=[l.strip() for l in text.splitlines()];free=next(l for l in clean if l.startswith('create_clock -name {free_clk}'))
    ddr=next(l for l in clean if l.startswith('create_generated_clock -name {ddrphy_sysclk}'))
    frequency=1000/float(re.search(r'-period \{([^}]+)',free)[1])*int(re.search(r'-multiply_by \{(\d+)',ddr)[1])/int(re.search(r'-divide_by \{(\d+)',ddr)[1])
    require(frequency==131.25,'DDR clock budget changed')
    return {'offline_exact_inventory':True,'U':368,'B':4,'retained':364,'budget_ns':15.238,'DDR_MHz':frequency,'runtime_CDB_replacement_proven':False}
