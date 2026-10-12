"""Check every explicit stage against original exported GTP parameter/port evidence."""
from pathlib import Path
import re,json,hashlib
P=Path(__file__).resolve().parent
net=P.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_11/actual/synthesis_export/synthesis_dump.v'
data=net.read_bytes()
pat=rb'(GTP_DFF_\w+)\s*/\*\s*(.*?)\s*\*/\s*#\(((?:[^()]|\([^()]*\))*)\)\s*[^\(]+\(((?:[^()]|\([^()]*\))*)\);'
found=[]; snippets=[]
for m in re.finditer(pat,data,re.S):
    typ,name,params,ports=m.groups()
    name=name.strip().lstrip(b'\\').strip()
    if not re.search(rb'(?:^|/|\.)(?:ack_sync|req_sync|overrun_sync|cr|hr|reset_pipe)\[\d\]$',name):continue
    pp=dict(re.findall(rb'\.(\w+)\s*\(([^)]*)\)',params))
    pin=dict(re.findall(rb'\.(\w+)\s*\(([^)]*)\)',ports))
    value=1 if re.search(rb'(?:^|/|\.)(?:cr|hr|reset_pipe)\[',name) else 0
    assert pp[b'GRS_EN']==b'"TRUE"' and pp[b'INIT']==f"1'b{value}".encode(),(name,pp)
    assert typ in ([b'GTP_DFF_P',b'GTP_DFF_PE'] if value else [b'GTP_DFF_C',b'GTP_DFF_CE']), (name,typ)
    if b'CE' in pin:assert pin[b'CE'].strip() in [b"1'b1",b'VCC'],(name,pin)
    line=data[:m.start()].count(b'\n')+1
    found.append({'name':name.decode(),'type':typ.decode(),'line':line,
                  'parameters':{k.decode():v.decode() for k,v in pp.items()},
                  'ports':{k.decode():v.decode() for k,v in pin.items()}})
    snippets.append(f'FILE {net.resolve()} LINE {line}\n'+m.group().decode('ascii','replace'))
assert len(found)==60, len(found)
sync=sum(x['parameters']['INIT']=="1'b0" for x in found)
assert sync==28
src=(P/'rtl_primitive/v7_sfd_candidate.v').read_bytes()
bus=(P/'rtl_primitive/v7_sdt_bus.v').read_bytes()
assert len(re.findall(rb'GTP_DFF_CE #',src))==7
assert len(re.findall(rb'GTP_DFF_PE #',src))==4
assert len(re.findall(rb'GTP_DFF_PE #',bus))==4
assert not re.search(rb'\b(?:cr|hr|ack_sync|req_sync|overrun_sync|reset_pipe)\s*<=',src+bus)
result={'original_netlist':str(net.resolve()),'netlist_sha256':hashlib.sha256(data).hexdigest(),
        'original_stage_count':len(found),'original_sync_count':sync,'original_reset_count':60-sync,
        'primitive_definition_sync':7,'primitive_definition_reset':8,'all_original_INIT_GRS_and_reset_type_checked':True,
        'CE_equivalence':'Original unconditional DFF_P/C becomes DFF_PE/CE with CE=1; any existing CE asserted constant checked.',
        'original_stages':found,'physical_mapping_verified':False}
(P/'evidence/primitive_parameter_audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
(P/'evidence/original_primitive_stage_extract.txt').write_text('\n\n'.join(snippets),encoding='utf8')
manifest=json.loads((P/'evidence/frozen_inputs.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items())
manifest[str(net.resolve())]=hashlib.sha256(data).hexdigest()
(P/'evidence/frozen_inputs.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print('ORIGINAL_60_STAGE_INIT_GRS_RESET_CE_AUDIT_PASS; candidate 28 CE + 32 PE.')
