"""Independent byte-level structural audit of the isolated replacement sources."""
from pathlib import Path
import re, json, hashlib
P=Path(__file__).resolve().parent
def normalize(data):
    aliases=dict(re.findall(rb'\(\* syn_keep=1 \*\) wire (\w+) = ([^;]+);',data))
    data=re.sub(rb'\(\* syn_keep=1 \*\) wire \w+ = [^;]+;',b'',data)
    for name,rhs in aliases.items():
        data=re.sub(rb'\b'+name+rb'\b',lambda m:rhs,data)
    data=re.sub(rb'\(\*.*?\*\)',b'',data,flags=re.S)
    data=re.sub(rb'//[^\r\n]*',b'',data)
    data=re.sub(rb'\s+',b'',data)
    data=data.replace(b'{req_sync[1],req_sync[0],request}',b'{req_sync[1:0],request}')
    data=data.replace(b"{reset_pipe[2],reset_pipe[1],reset_pipe[0],1'b0}",b"{reset_pipe[2:0],1'b0}")
    data=data.replace(b'reg[1:0]cr;reg[1:0]hr;',b'reg[1:0]cr,hr;')
    return data
result={}
for name in ['v7_sfd_candidate.v','v7_sdt_bus.v']:
    old=(P/'baseline'/name).read_bytes()
    new=(P/'rtl'/name).read_bytes()
    assert normalize(old)==normalize(new),name+' functional body changed'
    result[name]={'normalized_body_identical':True,
                  'baseline_sha256':hashlib.sha256(old).hexdigest(),
                  'candidate_sha256':hashlib.sha256(new).hexdigest(),
                  'kept_d_nets_per_definition':len(re.findall(rb'\(\* syn_keep=1 \*\) wire',new))}
    assert re.findall(rb'\bmodule\s+(\w+)',old)==re.findall(rb'\bmodule\s+(\w+)',new)
result['integration']='Replacement files only; do not add baseline and candidate to one PDS source list.'
result['physical_mapping_verified']=False
(P/'evidence/structural_audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
