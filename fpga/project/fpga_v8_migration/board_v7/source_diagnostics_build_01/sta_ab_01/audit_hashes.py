from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent;BUILD=HERE.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    result={}
    for name in ['protected_before.json','inputs_before.json']:
        old=json.loads((BUILD/name).read_bytes()); mismatch=[]
        # Hash manifests created by prepare.py are simple path -> sha dictionaries.
        for p,h in old.items():
            f=Path(p)
            if not f.is_absolute():f=BUILD/f
            actual=sha(f) if f.is_file() else None
            if actual!=h:mismatch.append({'path':str(f),'expected':h,'actual':actual})
        result[name]={'count':len(old),'mismatches':mismatch}
    result['original_six_fdc']={str(p):sha(p) for p in (BUILD/'inputs/source/constraints').glob('*.fdc')}
    result['synthesis_db']=sha(BUILD/'synthesize/v7_sdt_top_syn.adf')
    (HERE/'hash_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='original_six_fdc'},indent=2))
if __name__=='__main__':main()
