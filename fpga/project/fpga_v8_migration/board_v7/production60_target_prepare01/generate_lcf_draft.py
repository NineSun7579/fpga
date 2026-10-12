"""Generate isolated constraints from the exact independently reviewed syntax."""
from pathlib import Path
import hashlib,json,re
H=Path(__file__).resolve().parent
REVIEW=H.parent/'diagnostic_sync_register_map12/independent_review01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    result=REVIEW/'independent_result.json'
    assert sha(result)=='73046f8ae1292180d1d2c12dcfe6540270104ec76366906805ac137efd7ea74e'
    reference=REVIEW/'production60_syntax_reference.json'
    syntax=json.loads(reference.read_bytes())
    planfile=H/'site_candidate_plan.json';plan=json.loads(planfile.read_bytes())
    expected={r['target']:r['site'] for r in plan['rows']}
    # Accept only a syntax reference whose actual backend objects and sites
    # match the prepared target inventory exactly; no guessed dotted conversion.
    lists=[v for v in syntax.values() if isinstance(v,list) and len(v)==60 and all(isinstance(x,str) for x in v)]
    backend=[]
    for lines in lists:
        parsed=[]
        for line in lines:
            m=re.fullmatch(r'define_attribute \{i:([^}]+)\} \{PAP_LOC\} \{(CLMA_\d+_\d+)\}',line)
            if m:parsed.append(m.groups())
        if len(parsed)==60 and dict(parsed)==expected and len(dict(parsed))==60:backend=lines
    assert len(backend)==60,'Reviewed backend syntax must exactly match targets/sites'
    output=H/'production60_site_DRAFT.lcf';assert not output.exists()
    output.write_text('# PREPARATION ONLY: bind against fresh full synthesis before dev_map.\n'+'\n'.join(backend)+'\n',encoding='ascii')
    (H/'constraint_draft_binding.json').write_text(json.dumps({'status':'DRAFT_NOT_APPLIED',
        'review_sha256':sha(result),'syntax_reference_sha256':sha(reference),'site_plan_sha256':sha(planfile),
        'draft_sha256':sha(output),'targets':60,'distinct_sites':len(set(expected.values())),
        'fresh_build04_graph_bound':False,'production_mapping_PASS':False},indent=2),encoding='ascii')
    print('60 exact reviewed backend objects/sites bound in isolated LCF draft; fresh synthesis binding pending')
if __name__=='__main__':main()
