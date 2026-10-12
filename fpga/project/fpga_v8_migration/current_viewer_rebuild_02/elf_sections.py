"""Inspect frozen/rebuilt ELF bytes locally without executing any target image."""
import hashlib
import json
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'current_viewer_binding_02/inputs/userdata/linaro/detview-driving-demo-src'

def inspect(path):
    data=path.read_bytes()
    assert data[:6]==b'\x7fELF\x02\x01'
    offset=struct.unpack_from('<Q',data,40)[0]
    size,count,names_index=struct.unpack_from('<HHH',data,58)
    headers=[struct.unpack_from('<IIQQQQIIQQ',data,offset+i*size) for i in range(count)]
    n=headers[names_index]; names=data[n[4]:n[4]+n[5]]
    result={}
    for h in headers:
        start=h[0]; end=names.find(b'\0',start); name=names[start:end].decode('ascii','replace')
        content=b'' if h[1]==8 else data[h[4]:h[4]+h[5]]
        result[name]={'type':h[1],'flags':h[2],'bytes':h[5],'sha256':hashlib.sha256(content).hexdigest()}
        if name=='.comment':result[name]['strings']=[s for s in content.rstrip(b'\0').decode('ascii','replace').split('\0') if s]
    return {'path':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'machine':struct.unpack_from('<H',data,18)[0],'sections':result}

def main():
    frozen={p.name:inspect(p) for p in sorted(SOURCE.glob('*.o'))}
    frozen['detview']=inspect(SOURCE/'detview')
    rebuilt={p.name:inspect(p) for p in sorted((HERE/'rebuilt').glob('*')) if p.suffix=='.o' or p.name=='detview'}
    comparison={name:{'byte_identity':rec['sha256']==rebuilt[name]['sha256'],'different_sections':[s for s in sorted(set(rec['sections'])|set(rebuilt[name]['sections'])) if rec['sections'].get(s)!=rebuilt[name]['sections'].get(s)]} for name,rec in frozen.items() if name in rebuilt}
    (HERE/'local_elf_section_comparison.json').write_text(json.dumps({'frozen':frozen,'rebuilt':rebuilt,'comparison':comparison},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'baseline_objects':len(frozen)-1,'rebuilt_products':len(rebuilt),'products_section_equal':sum(not c['different_sections'] for c in comparison.values()),'baseline_compilers':sorted({c for p in frozen.values() for c in p['sections']['.comment']['strings']})}))

if __name__=='__main__':main()
