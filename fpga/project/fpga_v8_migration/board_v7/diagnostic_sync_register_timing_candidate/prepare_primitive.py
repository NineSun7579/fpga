"""Explicit GTP candidate, using installed primitive semantics and routed INIT evidence."""
from pathlib import Path
import re,json,hashlib,difflib,pymupdf
P=Path(__file__).resolve().parent
V=Path('C:/pango/PDS_2022.2-SP6.4')
for d in ['rtl_primitive','sim_primitive']:(P/d).mkdir(exist_ok=True)
proof=P.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_11/physical_target_bindings.json'
j=json.loads(proof.read_bytes())
summary={'source_file':str(proof.resolve()),'source_sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),
         'route_sha256':j['route_sha256'],'reset_logical':sum(len(x['logical_mappings']) for x in j['reset_bindings']),
         'reset_physical_RS':len(j['reset_bindings']),'packed_sync':j['sync_packed_internal']}
assert summary['reset_logical']==32 and summary['reset_physical_RS']==20
for x in j['reset_bindings']:
    for m in x['logical_mappings']:
        parms=m['parameters']
        assert m['assertion_value']==1 and parms['RS_MODE']=='ASYNC' and parms['GRS_EN']=='TRUE'
        assert parms.get('FF_INIT',parms.get('FF0_INIT'))=='1'
for x in j['sync_packed_internal']:
    assert x['parameters']['FF0_INIT']=='0' and x['parameters']['FFAPP0_INIT']=='0'
    assert x['parameters']['RS_MODE']=='ASYNC' and x['parameters']['GRS_EN']=='TRUE'
(P/'evidence/original_mapping_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')

def inst(name,width,clk,reset,set_value):
    primitive='GTP_DFF_PE' if set_value else 'GTP_DFF_CE'
    pin='P' if set_value else 'C'
    lines=[]
    for i in range(width):
        lines.append(f'    {primitive} #(.GRS_EN("TRUE"),.INIT(1\'b{set_value})) {name}_ff{i} '
                     f'(.Q({name}[{i}]),.D({name}_d{i}),.CLK({clk}),.{pin}({reset}),.CE(1\'b1));')
    return '\n'.join(lines).encode()+b'\n'

src=(P/'rtl/v7_sfd_candidate.v').read_bytes()
for name,width,clk,reset,set_value in [('cr',2,'cam_clk','reset_any',1),('hr',2,'host_clk','reset_any',1),
    ('ack_sync',2,'cam_clk','rst_c',0),('req_sync',3,'host_clk','rst_h',0),('overrun_sync',2,'host_clk','rst_h',0)]:
    src,n=re.subn(rb'\(\* syn_preserve=1, syn_allow_retiming=0, syn_srlstyle="registers" \*\) reg \['+
        str(width-1).encode()+rb':0\] '+name.encode()+rb';',
        lambda m:f'(* syn_keep=1 *) wire [{width-1}:0] {name};'.encode(),src)
    assert n==1
    if name in ['cr','hr']:
        pat=rb'    always @\(posedge '+clk.encode()+rb' or posedge reset_any\)\s*if\(reset_any\) '+name.encode()+rb'<=3; else '+name.encode()+rb'<=\{[^;]+;'
        src,n=re.subn(pat,lambda m:inst(name,width,clk,reset,set_value).rstrip(),src)
        assert n==1
    else:
        # Remove only these synchronizer assignments from original always blocks.
        src,n=re.subn(rb'\b'+name.encode()+rb'<=0;',b'',src)
        assert n==1
        src,n=re.subn(rb'\b'+name.encode()+rb'<=\{[^;]+;',b'',src)
        assert n==1
        marker=b'    reg [511:0] host_bank;' if name!='ack_sync' else b'    wire busy='
        src=src.replace(marker,inst(name,width,clk,reset,set_value)+marker)
bus=(P/'rtl/v7_sdt_bus.v').read_bytes()
bus=bus.replace(b'(* syn_preserve=1, syn_allow_retiming=0, syn_srlstyle="registers" *) reg [3:0] reset_pipe;',
                b'(* syn_keep=1 *) wire [3:0] reset_pipe;')
pat=rb'  always @\(posedge clk or posedge cam_reset\[g\] or posedge rst\)\s*if\(rst \|\| cam_reset\[g\]\) reset_pipe<=4\'hf;\s*else reset_pipe<=\{[^;]+;'
bus,n=re.subn(pat,lambda m:b'  (* syn_keep=1 *) wire reset_pipe_assert = rst | cam_reset[g];\n'+
    inst('reset_pipe',4,'clk','reset_pipe_assert',1).rstrip(),bus)
assert n==1
for name,new in [('v7_sfd_candidate.v',src),('v7_sdt_bus.v',bus)]:
    (P/'rtl_primitive'/name).write_bytes(new)
    old=(P/'baseline'/name).read_bytes()
    (P/'evidence'/(name+'.primitive.diff')).write_text(''.join(difflib.unified_diff(
        old.decode('ascii').splitlines(True),new.decode('ascii').splitlines(True),
        fromfile='frozen/'+name,tofile='primitive/'+name)),encoding='ascii')
for f in (P/'sim').glob('*'):
    if f.suffix not in ['.v','.sv','.vh']:continue
    data=f.read_bytes()
    if f.suffix=='.sv':
        module=b'module tb_v7_sfd_candidate;' if f.name=='tb_source.sv' else b'module tb_v7_sdb;'
        data=data.replace(module,module+b'\n GTP_GRS GRS_INST (.GRS_N(1\'b1));')
    (P/'sim_primitive'/f.name).write_bytes(data)
manifest=json.loads((P/'evidence/frozen_inputs.json').read_text())
extra=[proof,V/'doc/Pango_Design_Suite_User_Guide.pdf',
       P.parent/'physical_subagent_evidence_01/fixed_06/stage_api12/shell.log']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items())
for p in extra:manifest[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
(P/'evidence/frozen_inputs.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
d=pymupdf.open(extra[1])
(P/'docs/Pango_Design_Suite_User_Guide.txt').write_text('\n'.join(
    f'FILE: {extra[1]}\nPDF PAGE: {n}\n'+d[n-1].get_text() for n in [107,250,252]),encoding='utf8')
(P/'docs/stored_stage_api12_shell.log').write_bytes(extra[2].read_bytes())
print('Prepared explicit primitives: per camera CE 7, PE 8; INIT sync=0 reset=1; CE always 1; GRS_EN TRUE.')
