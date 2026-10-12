"""Byte-preserving isolated derivatives; never writes frozen inputs."""
from pathlib import Path
import re, hashlib, json, difflib
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
B=P.parent/'source_diagnostics_bus_candidate'
S=P.parent/'source_frame_diagnostics_candidate'
ports=dict(awvalid=1,awready=1,awaddr=32,wvalid=1,wready=1,wdata=32,wstrb=4,bvalid=1,bready=1,bresp=2,arvalid=1,arready=1,araddr=32,rvalid=1,rready=1,rdata=32,rresp=2)
taps=['clk','reset','raw_vsync','raw_href','raw_byte_accept','capture_vsync','capture_valid']
changes={}
operations=[]
pinfile=P/'input_pins.json'
pins=json.loads(pinfile.read_text()) if pinfile.exists() else {}
if pins:
    for f,h in pins.items(): assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h,('Pinned input changed',f)
def replace(b,a,c,n=1):
    assert b.count(a)==n,(a,b.count(a),n)
    operations.append({'old':a.decode('ascii','backslashreplace'),'new':c.decode('ascii','backslashreplace'),'matches':n})
    return b.replace(a,c)
def save(src,name,b):
    old=src.read_bytes(); (P/name).write_bytes(b)
    (P/(name+'.diff')).write_text(''.join(difflib.unified_diff(old.decode('gbk',errors='replace').splitlines(True),b.decode('gbk',errors='replace').splitlines(True),fromfile=str(src),tofile=name)),encoding='utf-8')
    changes[str(src)]=hashlib.sha256(old).hexdigest()
    return P/name
def add_ports(b):
    matches=list(re.finditer(rb'\)\(\r*\n',b)); assert len(matches)==1
    a=matches[0].group()
    return replace(b,a,a+''.join('    output wire diag_'+x+',\n' for x in taps).encode())
src=F/'rtl/ov5640_tc03_binding.v'; b=src.read_bytes()
b=replace(b,b'module ov5640 #(',b'module v7_sdt_binding #(')
b=add_ports(b)
expr=['cam_pclk','!ov_rst_n | !cam_rst_n','capture_vsync','cam_href','cam_href','cmos_frame_vsync_r','cmos_frame_valid_r']
b=replace(b,b'endmodule',('\n'+''.join('assign diag_'+x+' = '+y+';\n' for x,y in zip(taps,expr))+'endmodule').encode())
binding=save(src,'v7_sdt_binding.v',b)
src=F/'rtl/parent_tc04_c40cee500c37.v'; b=src.read_bytes()
b=replace(b,b'module ov5640_top #(',b'module v7_sdt_camera #(')
b=add_ports(b); b=replace(b,b'ov5640 #(',b'v7_sdt_binding #(')
b=replace(b,b'.ov_rst_n',(''.join('.diag_'+x+'(diag_'+x+'),\n        ' for x in taps)+'.ov_rst_n').encode())
parent=save(src,'v7_sdt_camera.v',b)
src=F/'rtl/fpga_v8_cooperative_top_v2_rfg01.v'; b=src.read_bytes()
b=replace(b,b'module fpga_v8_cooperative_top_v2_rfg01 #(',b'module v7_sdt_top #(')
b=replace(b,b'ov5640_top #(',b'v7_sdt_camera #(',4)
for i in range(4):
    anchor=f'.motion_record(cam{i+1}_motion_record)'.encode()
    b=replace(b,anchor,(''.join('.diag_'+x+'(diag_'+x+f'[{i}]),\n    ' for x in taps)).encode()+anchor)
start=b.index(b'ovreg_axil_decode_tc01 ovreg_axil_decode_u ('); end=b.index(b');',start)+2
old=b[start:end]; new=old
for n in ports:
    new=replace(new,('ovreg_axil_'+n+')').encode(),('diag_legacy_'+n+')').encode())
b=b[:start]+new+b[end:]
lines=['wire [3:0] diag_'+x+';' for x in taps]
lines += ['wire '+('' if w==1 else f'[{w-1}:0] ')+'diag_legacy_'+n+';' for n,w in ports.items()]
lines += ['v7_sdb source_diagnostics (.clk(axi_clk), .rst(axi_rst),',','.join('.'+('cam_'+x if x in ['clk','reset'] else x)+'(diag_'+x+')' for x in taps)+',',','.join('.s_'+n+'(ovreg_axil_'+n+'), .m_'+n+'(diag_legacy_'+n+')' for n in ports)+');']
b=replace(b,b'ovreg_axil_decode_tc01 ovreg_axil_decode_u (',('\n'.join(lines)+'\n\novreg_axil_decode_tc01 ovreg_axil_decode_u (').encode())
b=replace(b,b'v7_sdb source_diagnostics',b'v7_sdt_bus source_diagnostics')
# Retired M00 write response inputs must be idle, not floating into arbitration.
for ch in ['aw','ar']:
    # Match whitespace exactly from the pinned source through a byte regex.
    matches=list(re.finditer(rb'\.s00_axi_'+ch.encode()+rb'len\s*\(pcie_axi_'+ch.encode()+rb'len\s*\)',b)); assert len(matches)==1
    b=replace(b,matches[0].group(),('.s00_axi_'+ch+'len({4\'b0000, pcie_axi_'+ch+'len})').encode())
for n,v in [('bid',"{AXI_ID_M_LEN{1'b0}}"),('bresp',"2'b00"),('buser',"1'b0"),('bvalid',"1'b0")]:
    pattern=rb'(\.m00_axi_'+n.encode()+rb'\s*\()( +)(\))'
    matches=list(re.finditer(pattern,b)); assert len(matches)==1
    old=matches[0].group(); new=matches[0].group(1)+v.encode()+b')'
    b=replace(b,old,new)
top=save(src,'v7_sdt_top.v',b)
srcbus=B/'v7_sdb.v';bb=srcbus.read_bytes()
bb=replace(bb,b'module v7_sdb (',b'module v7_sdt_bus (')
bb=replace(bb,b'// Never forward W ahead of AW: old decoder routes W using AW selection.',b'// Offer AW and W together: frozen CAM requires simultaneous valid.\n // Decoder uses live AW route while AWVALID, saved route after AW handshake.')
bb=replace(bb,b'assign m_wvalid=ah && wh && !hit(wa) && wasent && !wdsent && !s_bvalid;',b'assign m_wvalid=ah && wh && !hit(wa) && !wdsent && !s_bvalid;')
buslocal=save(srcbus,'v7_sdt_bus.v',bb)
# Exact source list registered in the frozen project, substituting ONLY these three.
sub={str(src):top,str(F/'rtl/parent_tc04_c40cee500c37.v'):parent,str(F/'rtl/ov5640_tc03_binding.v'):binding}
paths=[]
for raw in re.findall(rb'\(_file "([^"]+\.v)"', (F/'project.pds').read_bytes()):
    f=F/raw.decode(); f=sub.get(str(f),f)
    if f not in paths: paths.append(f)
paths += [buslocal,S/'v7_sfd_candidate.v']
for f in paths:
    assert f.exists(),f
    assert 'cdc_boundary' not in str(f)
    changes.setdefault(str(f),hashlib.sha256(f.read_bytes()).hexdigest())
modules={}
for f in paths:
    clean=re.sub(rb'/\*.*?\*/|//[^\r\n]*',b'',f.read_bytes(),flags=re.S)
    for name in re.findall(rb'\bmodule\s+(\w+)',clean): modules.setdefault(name.decode(),[]).append(str(f))
conflicts={k:v for k,v in modules.items() if len(v)>1}
assert not conflicts,conflicts
(P/'module_scan.json').write_text(json.dumps({'registered_modules':len(modules),'conflicts':conflicts},indent=2))
(P/'sources.json').write_text(json.dumps([str(f) for f in paths],indent=2))
(P/'source_hashes.json').write_text(json.dumps(changes,indent=2))
(P/'generation_operations.json').write_text(json.dumps(operations,indent=2))
if not pins:
    pinfile.write_text(json.dumps({f:h for f,h in changes.items() if P not in Path(f).parents},indent=2))
print('GENERATED top/parent/binding plus corrected bus; duplicate modules=0')
