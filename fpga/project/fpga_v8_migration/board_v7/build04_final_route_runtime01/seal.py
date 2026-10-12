"""Seal reviewable new runtime and generated plans; never seals physical PASS."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    paths=list((HERE/'runtime').glob('*.py'))+list(HERE.glob('*.py'))+list((HERE/'commands').glob('*.tcl'))+list((HERE/'constraints').glob('*'))
    paths += [HERE/n for n in ['candidate_specific_expectation_contract.json','route_copy_plan.json','official_commands.json','signoff_manifest.json','coverageproof.json','reuse_ledger.json','input_before.json']]
    seal={p.relative_to(HERE).as_posix():sha(p) for p in paths}
    (HERE/'runtime_seal.json').write_text(json.dumps(seal,indent=2)+'\n',encoding='ascii')
    print('Sealed',len(seal),'runtime/constraint/command/plan files; no physical acceptance')
if __name__=='__main__':main()
