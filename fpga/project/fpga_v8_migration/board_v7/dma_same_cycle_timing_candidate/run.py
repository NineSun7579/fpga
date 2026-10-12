"""Isolated exact09 byte-preserving RTL candidate; vendor ModelSim only."""
from pathlib import Path
import ast, hashlib, json, re, subprocess, difflib

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
BASE = BOARD.parent
OUT = HERE / 'sim'
SIM = Path(r'C:\modeltech64_10.6e\win64')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def run(args, label):
    result = subprocess.run([str(x) for x in args], cwd=OUT, capture_output=True, timeout=120)
    data = result.stdout + result.stderr
    (OUT / (label + '.log')).write_bytes(data)
    assert result.returncode == 0 and b'** Error' not in data and b'** Fatal' not in data, data.decode(errors='replace')
    return data

def main():
    for folder in ['original', 'rtl', 'sim', 'evidence']:
        (HERE / folder).mkdir(exist_ok=True)
    source = BOARD / 'source_diagnostics_route_02/rtl/axi_dma_write_tc04.v'
    stream = BOARD / 'source_diagnostics_route_02/inputs/source/axi_dma/stream_pipe.v'
    exact = BOARD / 'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json'
    hashes = json.loads(exact.read_text())
    assert hashes['rtl\\axi_dma_write_tc04.v'] == sha(source)
    assert hashes['inputs\\source\\axi_dma\\stream_pipe.v'] == sha(stream)
    binding=exact.parent/'standard_flow_exact09.pds'
    assert b'(_file "rtl/axi_dma_write_tc04.v"' in binding.read_bytes()
    protected = [source, stream, exact, binding]
    for folder in ['source_diagnostics_timing_build_01', 'source_diagnostics_timing_build_02', 'diagnostic_sync_register_map_01']:
        protected += [p for p in (BOARD / folder).rglob('*') if p.is_file() and
                      (p.suffix.lower() in ['.v', '.sv', '.py', '.ps1', '.tcl', '.do', '.pds', '.fdc'])]
    before = {str(p): sha(p) for p in protected}
    raw = source.read_bytes()
    (HERE / 'original/axi_dma_write_tc04.v').write_bytes(raw)
    # Replace ASCII byte spans only. Preserve all other bytes, including GBK comments.
    edits = [
        (b'(!burst_trans || w_progress || data_in_valid || !t_m_axi_wready)',
         b'(!burst_trans || data_in_valid || !t_m_axi_wready)'),
        (re.search(rb'assign abort_done = trans && failed &&\s*\(b_fire \|\| \(abort_r && !burst_trans && !m_axi_awvalid\)\);',raw)[0],
         b'assign abort_done = trans &&\n    ((b_fire && (abort_r || abort_req || m_axi_bresp[1])) ||\n     (abort_r && !burst_trans && !m_axi_awvalid));')]
    # Preserve source newline style.
    if b'\r\n' in raw:
        edits = [(a.replace(b'\n', b'\r\n'), b.replace(b'\n', b'\r\n')) for a,b in edits]
    candidate = raw
    for old, new in edits:
        assert candidate.count(old) == 1, old
        candidate = candidate.replace(old, new, 1)
    # Both simulation and delivered candidate use unique module names.
    oldname = b'module axi_dma_write_tc04'
    reference = raw.replace(oldname, b'module axi_dma_write_dma_sc_reference', 1)
    candidate = candidate.replace(oldname, b'module axi_dma_write_dma_sc_candidate', 1)
    refpath = HERE / 'original/axi_dma_write_dma_sc_reference.v'
    dutpath = HERE / 'rtl/axi_dma_write_dma_sc_candidate.v'
    refpath.write_bytes(reference)
    dutpath.write_bytes(candidate)
    (HERE / 'original/stream_pipe.v').write_bytes(stream.read_bytes())
    restored = candidate.replace(b'module axi_dma_write_dma_sc_candidate', oldname, 1)
    for old,new in reversed(edits):
        assert restored.count(new) == 1
        restored = restored.replace(new, old, 1)
    assert restored == raw
    (HERE / 'evidence/candidate.patch').write_text(''.join(difflib.unified_diff(
        raw.decode('gbk').splitlines(True), candidate.decode('gbk').splitlines(True),
        fromfile='exact09/axi_dma_write_tc04.v', tofile='isolated/axi_dma_write_dma_sc_candidate.v')), encoding='utf-8')
    # Reuse existing TC02 public-port parser and actual bus stimulus; never invoke main().
    runner = BASE / 'timing_correction_02/run_dma_tests.py'
    text = runner.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    construction = '\n'.join(ast.get_source_segment(text,n) for n in node.body if 20 <= n.lineno <= 56)
    construction = construction.replace("('axi_dma_write','old')", "('axi_dma_write_dma_sc_reference','old')")
    construction = construction.replace("('axi_dma_write_tc02','new')", "('axi_dma_write_dma_sc_candidate','new')")
    env = dict(raw=raw, re=re)
    exec(compile(construction, str(runner)+':reused', 'exec'), env)
    lines = env['lines']
    internals = ['len','addr','trans','burst_trans','act_burst_len','wd_cnt','abort_r','available_q','w_done',
                 'burst_len','max_burst_len','source_burst_ready','waiting_source','wd_clear','wd_step','w_progress','failed','abort_done',
                 't_m_axi_wvalid','t_m_axi_wready','t_m_axi_wdata','t_m_axi_wstrb','t_m_axi_wlast']
    check = 'if({' + ','.join('old_dut.'+n for n in internals) + '} !== {' + ','.join('new_dut.'+n for n in internals) + '}) $fatal(1,"full internal mismatch");'
    idx = next(i for i,line in enumerate(lines) if 'beat count mismatch' in line)
    lines[idx] = check
    # Add WIDTH/BURST parameters without changing stimulus semantics.
    lines[1] = 'module tb_dma_tc02; parameter integer WAIT=1, WIDTH=128, BURST=16;'
    lines = [line.replace('[128 - 1:0]', '[WIDTH - 1:0]').replace('[16 - 1:0]', '[WIDTH/8 - 1:0]')
             .replace('.BURST_LEN(16)', '.BURST_LEN(BURST),.DATA_WIDTH(WIDTH)') for line in lines]
    # Keep the existing 80-case harness, broaden boundary addresses/lengths.
    lines = [line.replace("cmd_addr=32'h01800ff0;", "cmd_addr=32'h01800000 + ((i%8)==0 ? 0 : (i%8)==1 ? 16 : (i%8)==2 ? 2048 : (i%8)==3 ? 3840 : (i%8)==4 ? 4080 : (i%8)==5 ? 4096 : (i%8)==6 ? 8192 : 32'hfff0);")
             .replace('default:size=$urandom;', '10:size=31;11:size=32;12:size=33;13:size=255;14:size=256;15:size=257;16:size=4080;17:size=4081;18:size=4095;19:size=4097;default:size=$urandom;')
             for line in lines]
    original = OUT / 'tb_dma_original.sv'
    counters='''integer aw_count=0,w_count=0,lastw_count=0,b_count=0,berr_count=0,abort_count=0,reset_cycles=0,aw_stalls=0,w_stalls=0;
always @(posedge clk) begin
    if(rst) reset_cycles=reset_cycles+1;
    else begin
        if(old_m_axi_awvalid && m_axi_awready) aw_count=aw_count+1;
        if(old_m_axi_wvalid && m_axi_wready) begin w_count=w_count+1; if(old_m_axi_wlast) lastw_count=lastw_count+1; end
        if(old_m_axi_bready && m_axi_bvalid) begin b_count=b_count+1; if(m_axi_bresp[1]) berr_count=berr_count+1; end
        if(old_data_in_abort) abort_count=abort_count+1;
        if(old_m_axi_awvalid && !m_axi_awready) aw_stalls=aw_stalls+1;
        if(old_m_axi_wvalid && !m_axi_wready) w_stalls=w_stalls+1;
    end
end'''
    count_display='$display("BUS_COUNTS aw=%0d w=%0d lastw=%0d b=%0d berr=%0d abort=%0d resetcycles=%0d awstalls=%0d wstalls=%0d",aw_count,w_count,lastw_count,b_count,berr_count,abort_count,reset_cycles,aw_stalls,w_stalls);'
    idx=lines.index('always #4 clk=~clk;')
    lines.insert(idx,counters)
    lines=[line.replace('$display("DMA_TC02_PASS',count_display+'$display("DMA_TC02_PASS') for line in lines]
    original.write_text('\n'.join(lines), encoding='ascii')
    prefix = lines[:lines.index('always #4 clk=~clk;')]
    prefix[1] = 'module tb_dma_edges; parameter integer WAIT=1, WIDTH=128, BURST=16; parameter LIMIT=7;'
    prefix = [line.replace('.BURST_LEN(BURST)', '.BURST_LEN(BURST),.WD_LIMIT(LIMIT)') for line in prefix]
    bodypath = BASE / 'timing_correction_04/tests/dma_edges_body.sv'
    body = bodypath.read_text().replace('@OLDBUS@',env['oldbus']).replace('@NEWBUS@',env['newbus'])
    body = body.replace('cycles=cycles+1;', check + '\n    cycles=cycles+1;')
    body = body.replace('$display("DMA_TC04_EDGES_PASS',count_display+'\n    $display("DMA_TC04_EDGES_PASS')
    edge = OUT / 'tb_dma_edges.sv'
    edge.write_text('\n'.join(prefix) + '\n' + body, encoding='ascii')
    priority = OUT / 'tb_dma_priority.sv'
    priority_prefix = [line.replace('module tb_dma_edges;', 'module tb_dma_priority;') for line in prefix]
    priority_body = (HERE / 'tb_priority_body.svh').read_text().replace('@CHECK@',check).replace('@OLDBUS@',env['oldbus']).replace('@NEWBUS@',env['newbus'])
    priority.write_text('\n'.join(priority_prefix)+'\n'+priority_body, encoding='ascii')
    # Exhaust original and proposed expressions over independent four-state scalar inputs.
    xtb = OUT / 'tb_fourstate.sv'
    xtb.write_text((HERE / 'tb_fourstate.sv').read_text(), encoding='ascii')
    run([SIM/'vlib.exe','work'],'vlib')
    run([SIM/'vlog.exe','-sv',HERE/'original/stream_pipe.v',refpath,dutpath,original,edge,priority,xtb], 'compile')
    records=[]
    def counts(data):
        match=re.search(rb'BUS_COUNTS aw=(\d+) w=(\d+) lastw=(\d+) b=(\d+) berr=(\d+) abort=(\d+) resetcycles=(\d+) awstalls=(\d+) wstalls=(\d+)',data)
        assert match
        return dict(zip(['aw','w','lastw','b','berr','abort','reset_cycles','aw_stalls','w_stalls'],map(int,match.groups())))
    for wait in [0,1]:
        for width,burst in [(128,16),(64,8),(256,32),(128,1),(128,255)]:
            label=f'original_wait_{wait}_width_{width}_burst_{burst}'
            data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_tc02',f'-gWAIT={wait}',f'-gWIDTH={width}',f'-gBURST={burst}','-do','run -all; quit -f'], label)
            assert b'DMA_TC02_PASS cases=80' in data
            records.append(dict(label=label,cases=80,bus_counts=counts(data)))
        for limit in [0,1,7,16777215]:
            label=f'edges_wait_{wait}_limit_{limit}'
            data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_edges',f'-gWAIT={wait}',f'-gLIMIT={limit}','-do','run -all; quit -f'],label)
            match=re.search(rb'DMA_TC04_EDGES_PASS cycles=(\d+) vectors=(\d+) natural=(\d+)',data)
            assert match
            records.append(dict(label=label,cycles=int(match[1]),vectors=int(match[2]),natural=int(match[3]),bus_counts=counts(data),bus_count_note='Includes paired internal-deposit vectors; natural scenario counts reported separately.'))
    data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_fourstate','-do','run -all; quit -f'],'fourstate')
    assert b'FOURSTATE_PASS' in data
    for width in [64,128,256]:
        label=f'priority_width_{width}'
        pdata=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_priority',f'-gWIDTH={width}','-do','run -all; quit -f'],label)
        match=re.search(rb'PRIORITY_PASS vectors=(\d+)',pdata)
        assert match
        records.append(dict(label=label,priority_vectors=int(match[1])))
    assert all(sha(Path(p)) == h for p,h in before.items())
    result=dict(status='PASS',source=str(source),exact09_sha256=sha(source),candidate_sha256=sha(dutpath),
                reference_sha256=sha(refpath),exact09_manifest_sha256=sha(exact),byte_roundtrip=True,
                protected_sources_scripts_unchanged=True,protected_files=len(before),simulations=records,
                original_cases=sum(r.get('cases',0) for r in records),
                edge_cycles=sum(r.get('cycles',0) for r in records),vectors=sum(r.get('vectors',0) for r in records),
                natural_scenarios=sum(r.get('natural',0) for r in records),
                priority_vectors=sum(r.get('priority_vectors',0) for r in records),
                fourstate_log=data.decode(errors='replace'),routed_timing_verified=False)
    (HERE/'evidence/results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (HERE/'evidence/protected_sha256.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    artifacts=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ['.v','.sv','.py','.log','.json','.patch'] and p.name != 'artifact_sha256.json']
    artifacts += [runner,bodypath,exact]
    (HERE/'evidence/artifact_sha256.json').write_text(json.dumps({str(p):sha(p) for p in artifacts},indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__ == '__main__':
    main()
