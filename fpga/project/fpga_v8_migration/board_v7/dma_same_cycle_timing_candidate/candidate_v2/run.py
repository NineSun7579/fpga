"""Actual exact09/v2 RTL ModelSim proof and cycle regression. Local writes only."""
from pathlib import Path
import hashlib, json, re, subprocess, difflib

HERE=Path(__file__).resolve().parent
V1=HERE.parent
BOARD=V1.parent
SIM=Path(r'C:\modeltech64_10.6e\win64')
OUT=HERE/'sim'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def run(args,label):
    r=subprocess.run([str(x) for x in args],cwd=OUT,capture_output=True,timeout=240)
    data=r.stdout+r.stderr
    (OUT/(label+'.log')).write_bytes(data)
    assert r.returncode==0 and b'** Error' not in data and b'** Fatal' not in data,data.decode(errors='replace')
    return data

def main():
    for d in ['original','rtl','sim','evidence']:(HERE/d).mkdir(exist_ok=True)
    frozen=[p for p in V1.rglob('*') if p.is_file() and HERE not in p.parents]
    for folder in ['source_diagnostics_timing_build_01','source_diagnostics_timing_build_02','diagnostic_sync_register_map_01']:
        frozen += [p for p in (BOARD/folder).rglob('*') if p.is_file() and p.suffix.lower() in ['.v','.sv','.py','.tcl','.ps1','.do','.pds','.fdc']]
    before={str(p):sha(p) for p in frozen}
    source=BOARD/'source_diagnostics_route_02/rtl/axi_dma_write_tc04.v'
    raw=source.read_bytes()
    assert sha(source)=='cfcac8a1987e0b443d5521b27ac508ba82cc4e9cec5ea269c8cf3f3af956a6e8'
    v1path=V1/'rtl/axi_dma_write_dma_sc_candidate.v'
    assert sha(v1path)=='82459c1c26166ade9b5b6732615141100100ce2387ea9fcc68844bc7dbe35ef2'
    candidate=v1path.read_bytes()
    old=re.search(rb'assign max_burst_len = [^\r\n]+;',candidate)[0]
    assert old in raw
    new=b'''// V2: only the proven signed 32-bit BURST_LEN/default byte-width domain.
localparam PAGE_ARITH_13_SUPPORTED =
    (DATA_WIDTH == 128) && (KEEP_WIDTH == 16) && (AXI_BURST_SIZE == 4) &&
    ($bits(BURST_LEN) == 32) && (BURST_LEN >= 0) && (BURST_LEN <= 255) &&
    !(BURST_LEN < -1);
generate
    if (PAGE_ARITH_13_SUPPORTED) begin : page_arith_13
        wire [12:0] page_offset = {1'b0, addr[11:0]};
        wire [12:0] burst_bytes = {1'b0, burst_len, 4'b0000};
        wire [12:0] page_sum = page_offset + burst_bytes;
        wire [12:0] page_remaining = 13'h1000 - page_offset;
        // Keep ?: unknown-condition bit merging and the original branch test.
        assign max_burst_len = ((page_sum >> 12) != 13'd0) ?
                              page_remaining[11:4] : burst_len;
    end else begin : page_arith_generic
        '''+old+b'''
    end
endgenerate'''
    if b'\r\n' in candidate:new=new.replace(b'\n',b'\r\n')
    assert candidate.count(old)==1
    candidate=candidate.replace(old,new,1).replace(b'module axi_dma_write_dma_sc_candidate',b'module axi_dma_write_dma_sc_v2',1)
    reference=raw.replace(b'module axi_dma_write_tc04',b'module axi_dma_write_dma_sc_v2_reference',1)
    (HERE/'original/axi_dma_write_tc04.v').write_bytes(raw)
    ref=HERE/'original/axi_dma_write_dma_sc_v2_reference.v'
    dut=HERE/'rtl/axi_dma_write_dma_sc_v2.v'
    ref.write_bytes(reference);dut.write_bytes(candidate)
    stream=HERE/'original/stream_pipe.v'
    stream.write_bytes((V1/'original/stream_pipe.v').read_bytes())
    assert candidate.replace(new,old,1).replace(b'module axi_dma_write_dma_sc_v2',b'module axi_dma_write_dma_sc_candidate',1)==v1path.read_bytes()
    assert candidate.count(old)==1
    for name in ['axi_dma_write_dma_sc_v2','axi_dma_write_dma_sc_v2_reference']:
        found=[str(p) for p in BOARD.rglob('*.v') if re.search(rb'\bmodule\s+'+name.encode()+rb'\b',p.read_bytes())]
        assert len(found)==1,found
    for label,base in [('from_exact09',raw),('from_v1',v1path.read_bytes())]:
        (HERE/f'evidence/{label}.patch').write_text(''.join(difflib.unified_diff(base.decode('gbk').splitlines(True),candidate.decode('gbk').splitlines(True),fromfile=label,tofile='candidate_v2')),encoding='utf-8')
    replacements=[(b'axi_dma_write_dma_sc_reference',b'axi_dma_write_dma_sc_v2_reference'),(b'axi_dma_write_dma_sc_candidate',b'axi_dma_write_dma_sc_v2')]
    tbs=[]
    for name in ['tb_dma_original.sv','tb_dma_edges.sv','tb_dma_priority.sv','tb_fourstate.sv']:
        b=(V1/'sim'/name).read_bytes()
        for a,c in replacements:b=b.replace(a,c)
        p=OUT/name;p.write_bytes(b);tbs.append(p)
    # Derive proof wiring from the existing actual-RTL miter API.
    text=tbs[0].read_text()
    prefix=text[:text.index('integer aw_count')]
    prefix=prefix.replace('module tb_dma_tc02; parameter integer WAIT=1, WIDTH=128, BURST=16;',
                          'module boundary_pair #(parameter BURST=8, WIDTH=128, KEEP=WIDTH/8, ID=0, EXPECT=1, EXHAUST=0)(output reg done=0); localparam WAIT=1;')
    prefix=prefix.replace('[WIDTH/8 - 1:0]','[KEEP - 1:0]').replace('.DATA_WIDTH(WIDTH)', '.DATA_WIDTH(WIDTH),.KEEP_WIDTH(KEEP)')
    body=(HERE/'tb_boundary_body.svh').read_text()
    proof=OUT/'tb_boundary.sv'
    proof.write_text(prefix+'\n'+body+'\n'+(HERE/'tb_boundary_top.sv').read_text(),encoding='ascii')
    run([SIM/'vlib.exe','work'],'vlib')
    run([SIM/'vlog.exe','-sv',stream,ref,dut,*tbs,proof],'compile')
    records=[]
    # Fail immediately, retaining the first counterexample, before full regression.
    data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_boundary','-do','run -all; quit -f'],'boundary_proof')
    assert b'BOUNDARY_ALL_PASS' in data
    pairs=re.findall(rb'BOUNDARY_PAIR_PASS id=(\d+) specialized=(\d+) binary=(\d+) fourstate=(\d+) credit=(\d+)',data)
    assert len(pairs)==12
    proof_records=[dict(zip(['id','specialized','binary','fourstate','credit'],map(int,m))) for m in pairs]
    for wait in [0,1]:
        for width,burst in [(128,16),(64,8),(256,32),(128,1),(128,255)]:
            label=f'original_wait_{wait}_width_{width}_burst_{burst}'
            data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_tc02',f'-gWAIT={wait}',f'-gWIDTH={width}',f'-gBURST={burst}','-do','run -all; quit -f'],label)
            assert b'DMA_TC02_PASS cases=80' in data
            records.append(dict(label=label,cases=80))
        for limit in [0,1,7,16777215]:
            label=f'edges_wait_{wait}_limit_{limit}'
            data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_edges',f'-gWAIT={wait}',f'-gLIMIT={limit}','-do','run -all; quit -f'],label)
            m=re.search(rb'DMA_TC04_EDGES_PASS cycles=(\d+) vectors=(\d+) natural=(\d+)',data);assert m
            records.append(dict(label=label,cycles=int(m[1]),vectors=int(m[2]),natural=int(m[3])))
    for width in [64,128,256]:
        label=f'priority_width_{width}'
        data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_priority',f'-gWIDTH={width}','-do','run -all; quit -f'],label)
        m=re.search(rb'PRIORITY_PASS vectors=(\d+)',data);assert m
        records.append(dict(label=label,priority_vectors=int(m[1])))
    data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_fourstate','-do','run -all; quit -f'],'v1_fourstate')
    assert b'FOURSTATE_PASS abort_vectors=16384 clear_vectors=65536' in data
    for r in records:
        data=(OUT/(r['label']+'.log')).read_bytes()
        m=re.search(rb'BUS_COUNTS aw=(\d+) w=(\d+) lastw=(\d+) b=(\d+) berr=(\d+) abort=(\d+) resetcycles=(\d+) awstalls=(\d+) wstalls=(\d+)',data)
        if m:r['bus_counts']=dict(zip(['aw','w','lastw','b','berr','abort','reset_cycles','aw_stalls','w_stalls'],map(int,m.groups())))
    changed=[p for p,h in before.items() if sha(Path(p))!=h]
    assert not changed,changed
    result=dict(status='PASS',exact09_sha256=sha(source),v1_sha256=sha(v1path),candidate_sha256=sha(dut),reference_sha256=sha(ref),
                v1_all_files_unchanged=True,protected_files=len(before),generic_expression_byte_identical=True,v2_to_v1_byte_roundtrip=True,
                boundary_proof=proof_records,simulations=records,original_cases=sum(r.get('cases',0) for r in records),
                edge_cycles=sum(r.get('cycles',0) for r in records),edge_vectors=sum(r.get('vectors',0) for r in records),
                natural_scenarios=sum(r.get('natural',0) for r in records),priority_vectors=sum(r.get('priority_vectors',0) for r in records),
                routed_timing_verified=False)
    (HERE/'evidence/results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (HERE/'evidence/protected_sha256.json').write_text(json.dumps(before,indent=2))
    artifacts=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ['.py','.v','.sv','.svh','.json','.patch','.log','.md'] and p.name!='artifact_sha256.json']
    (HERE/'evidence/artifact_sha256.json').write_text(json.dumps({str(p):sha(p) for p in artifacts},indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
