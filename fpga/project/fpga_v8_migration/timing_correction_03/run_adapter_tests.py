"""Isolated V4-vs-tc03 differential regression; never invokes PDS.

Generated testbenches, vector files and ModelSim libraries stay in adapter_artifacts.
Reads source bytes (including GBK sources) without changing production or V4.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MIGRATION = ROOT.parent
PROJECT = MIGRATION.parent
V4 = MIGRATION / 'whole_candidate_v4_route_01'
ORIGINAL = V4 / 'rtl/fpga_v8_ddr_adapter.v'
CANDIDATE = ROOT / 'rtl/fpga_v8_ddr_adapter_tc03.v'
CONTRACT = MIGRATION / 'ddr_adapter_contract'
ART = ROOT / 'adapter_artifacts'
SIM = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
LIMITS = [0x10000000, 0x1000, 0x100010, 0x100ff0, 0x10, 0xff0,
          0, 1, 0x100001, 0x10001000, 0xfffffff0, 0xffffffff,
          0x110000000, 0x100000000, 0x100000010]
SEED = 0x03dd2026

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def ports():
    header = ORIGINAL.read_bytes().split(b');', 1)[0]
    return [(d.decode(), (w or b'').decode(), n.decode()) for d, w, n in
            re.findall(rb'\b(input|output)\s+(?:wire|reg)\s*(\[[^\]]+\])?\s*(\w+)', header)]

def pair(decls, conn, limit="32'h10000000"):
    out = []
    for direction, width, name in ports():
        if direction == 'output':
            out.append(f'wire {width} tc03_{name};')
    out.append(f'fpga_v8_ddr_adapter_tc03 #(.DDR_ADDRESS_LIMIT({limit})) candidate (')
    out.append(',\n'.join(f'.{n}({"tc03_"+n if d=="output" else conn[n]})' for d, w, n in ports()) + ');')
    comparisons = '\n'.join(f'if ({conn[n]} !== tc03_{n}) $fatal(1,"PUBLIC_OUTPUT_DIFF {n} time=%0t",$time);'
                            for d, w, n in ports() if d == 'output')
    out.append('integer differential_samples=0;\ntask compare_public; begin\n' + comparisons +
               '\ndifferential_samples=differential_samples+1; end endtask\n'
               'always @(posedge clk) begin compare_public(); #1; compare_public(); end\n'
               'always @(negedge clk) begin #1; compare_public(); end\n')
    return '\n'.join(out)

def legal(raw_limit, addr, length, size, burst):
    limit = raw_limit & 0xffffffff  # Both RTL modules have a typed 32-bit parameter.
    return int(0 < limit <= 0x10000000 and limit % 16 == 0 and length <= 15
               and addr % 16 == 0 and size == 4 and burst == 1
               and addr % 4096 + (length + 1) * 16 <= 4096
               and addr + (length + 1) * 16 <= limit)

def vectors(raw_limit, index):
    rng = random.Random(SEED + index)
    limit = raw_limit & 0xffffffff
    result = []
    def add(addr, length=0, size=4, burst=1):
        addr &= 0xffffffff
        expected = legal(raw_limit, addr, length, size, burst)
        packed = (addr << 14) | (length << 6) | (size << 3) | (burst << 1) | expected
        result.append(f'{packed:012x}\n')
    # Exhaust the entire 8-bit LEN and aligned page offset domain on default.
    if index == 0:
        for beat in range(256):
            for length in range(256):
                add(beat * 16, length)
    for length in range(256):
        # Last legal, one beat over, start == limit, address overflow, 4KB edge.
        for addr in [limit - (length+1)*16, limit - length*16, limit, limit-16,
                     (limit & ~4095)-16, (limit & ~4095), 0xff0, 0x1000,
                     0x1000-(length+1)*16, 0x1000-length*16, 0xfffffff0, 0xffffffff]:
            add(addr, length)
    for low in range(16):
        for length in [0, 1, 15, 16, 127, 255]:
            add(low, length)
            add(limit-16+low, length)
    for size in range(8):
        for burst in range(4):
            for length in [0, 15, 16, 255]:
                add(0, length, size, burst)
    for _ in range(10000):
        addr = rng.choice([rng.getrandbits(32), rng.randrange(0x2000),
                           limit+rng.randrange(-8192, 8192), 0xffffffff-rng.randrange(8192)])
        length = rng.choice([rng.randrange(256), rng.randrange(16)])
        add(addr, length, rng.choice([4, 4, rng.randrange(8)]), rng.choice([1, 1, rng.randrange(4)]))
    return result

def boundary_tb():
    declarations = []
    for direction, width, name in ports():
        if name == 'clk':
            declarations.append('reg clk=0; always #5 clk=~clk;')
        else:
            declarations.append(f'{"reg" if direction=="input" else "wire"} {width} {name}' +
                                ('=0;' if direction=='input' else ';'))
    connections = {n: n for d, w, n in ports()}
    instance = 'fpga_v8_ddr_adapter #(.DDR_ADDRESS_LIMIT(RAW_LIMIT)) reference (\n' + \
        ',\n'.join(f'.{n}({n})' for d, w, n in ports()) + ');'
    base = '''`timescale 1ns/1ps
module adapter_boundary #(parameter [63:0] RAW_LIMIT=0, parameter N=1,
                           parameter VECTOR_FILE="vectors.hex") (output reg done=0);
DECLS
INSTANCE
PAIR
reg [45:0] vectors [0:N-1];
reg expected;
integer k, legal_count=0, rejected_count=0;
initial begin
  $readmemh(VECTOR_FILE,vectors);
  repeat(5) @(negedge clk); rst_n=1; repeat(3) @(negedge clk);
  for(k=0;k<N;k=k+1) begin
    {s_awaddr,s_awlen,s_awsize,s_awburst,expected}=vectors[k];
    {s_araddr,s_arlen,s_arsize,s_arburst}=vectors[k][45:1];
    // Illegal VALID requests must stay unaccepted and flag both directions.
    // Legal requests remain combinational probes here; transactions run separately.
    s_awvalid=!expected; s_arvalid=!expected;
    #1; compare_public();
    if(s_awready!==expected || s_arready!==expected)
      $fatal(1,"ORACLE_DIFF limit=%h index=%0d addr=%h len=%0d",RAW_LIMIT,k,s_awaddr,s_awlen);
    @(posedge clk); #2;
    if(!expected && (error_flags[1:0]!==2'b11 || v_awvalid || v_arvalid || write_busy || read_busy))
      $fatal(1,"INVALID_ACCEPTED_OR_UNFLAGGED limit=%h index=%0d",RAW_LIMIT,k);
    if(expected) legal_count=legal_count+1; else rejected_count=rejected_count+1;
    @(negedge clk);
  end
  s_awvalid=0; s_arvalid=0;
  $display("BOUNDARY_PASS raw_limit=%h effective_limit=%h vectors=%0d legal=%0d rejected=%0d public_samples=%0d",
           RAW_LIMIT,RAW_LIMIT[31:0],N,legal_count,rejected_count,differential_samples);
  done=1;
end
endmodule
'''
    base = base.replace('DECLS', '\n'.join(declarations)).replace('INSTANCE', instance).replace(
        'PAIR', pair(declarations, connections, 'RAW_LIMIT'))
    wrappers = []
    totals = []
    for index, limit in enumerate(LIMITS):
        data = vectors(limit, index)
        (ART/f'boundary_{index}.hex').write_text(''.join(data), encoding='ascii')
        wrappers.append(f'wire done_{index}; adapter_boundary #(.RAW_LIMIT(64\'h{limit:016x}), '
                        f'.N({len(data)}), .VECTOR_FILE("boundary_{index}.hex")) b{index}(done_{index});')
        totals.append(dict(raw_limit=hex(limit), effective_limit=hex(limit&0xffffffff), vectors=len(data)))
    base += '\nmodule tb_adapter_boundary;\n' + '\n'.join(wrappers) + '\ninitial begin wait(' + \
        ' && '.join(f'done_{i}' for i in range(len(LIMITS))) + \
        '); $display("ALL_BOUNDARY_PASS"); $finish; end\ninitial begin #2000000; $fatal(1,"boundary watchdog"); end\nendmodule\n'
    (ART/'tb_adapter_boundary.sv').write_text(base, encoding='ascii')
    return totals

def contract_tb():
    source = (CONTRACT/'tb_ddr_adapter_contract.sv').read_bytes().decode('ascii')
    block = re.search(r'fpga_v8_ddr_adapter dut \((.*?)\n    \);', source, re.S).group(1)
    connections = {}
    for d, w, n in ports():
        # Input v_wid has a nested parenthesized corruption expression.
        start = block.index('.'+n+'(') + len(n)+2
        pos=start; depth=1
        while depth:
            depth += (block[pos]=='(') - (block[pos]==')')
            pos+=1
        connections[n] = block[start:pos-1]
    source = source.replace('    fpga_v8_vendor_ddr_stub vendor (',
                            pair([], connections) + '\n    fpga_v8_vendor_ddr_stub vendor (', 1)
    source = source.replace('        $fclose(f);', '''
        // Fixed-seed concurrent random legal bursts, gaps and vendor stalls.
        for(random_tx=0;random_tx<128;random_tx=random_tx+1) begin
            random_state=random_state ^ (random_state<<13);
            random_state=random_state ^ (random_state>>17);
            random_state=random_state ^ (random_state<<5);
            random_wbeats=1+(random_state & 15);
            random_rbeats=1+((random_state>>8) & 15);
            fork
              begin
                hold_aw=1; hold_w=1;
                accept_aw(random_tx%16,100+random_tx,random_wbeats);
                send_words(100+random_tx,random_wbeats,0);
                tick(1+((random_state>>16)&7)); hold_aw=0;
                wait(vendor_wactive); tick(1+((random_state>>20)&7)); hold_w=0;
                retire_b(random_tx%16,0);
              end
              begin
                hold_ar=1; hold_r=1;
                accept_ar(random_tx%128,32'h00310000+random_tx*256,random_rbeats);
                tick(1+((random_state>>24)&7)); hold_ar=0;
                wait(vendor_ractive); tick(1+((random_state>>28)&7)); hold_r=0;
                drain_read(random_tx%128,32'h00310000+random_tx*256,random_rbeats);
              end
            join
            tick(3);
            if(flags!==0 || wb || rb) $fatal(1,"random transaction final state");
        end
        $display("RANDOM_TRANSACTION_PASS bursts_each_direction=128 seed=03dd2026 public_samples=%0d",differential_samples);
        $fclose(f);''', 1)
    source = source.replace('    integer cycles=0,',
                            "    integer random_tx,random_wbeats,random_rbeats;\n    reg [31:0] random_state=32'h03dd2026;\n    integer cycles=0,", 1)
    (ART/'tb_adapter_contract_diff.sv').write_text(source, encoding='ascii')

def run(args, directory, log):
    proc = subprocess.run([str(a) for a in args], cwd=directory, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=600)
    (directory/log).write_bytes(proc.stdout)
    text=proc.stdout.decode(errors='replace')
    if proc.returncode or re.search(r'\*\* (Error|Fatal):', text):
        raise RuntimeError(text[-8000:])
    return text

def main():
    ART.mkdir(exist_ok=True)
    # Check module uniqueness before compiling; GBK-safe byte scan.
    collisions = [p for p in PROJECT.rglob('*.v') if p != CANDIDATE and
                  re.search(rb'\bmodule\s+fpga_v8_ddr_adapter_tc03\b', p.read_bytes())]
    assert not collisions, collisions
    original = ORIGINAL.read_bytes().replace(b'\r\n', b'\n')
    candidate = CANDIDATE.read_bytes().replace(b'\r\n', b'\n')
    # All state, assignments and FIFO wiring outside the predicate region must match.
    assert original.split(b'    assign s_awready',1)[1] == candidate.split(b'    assign s_awready',1)[1]
    assert original.split(b'    wire [63:0] aw_end',1)[0].split(b') (',1)[1] == \
           candidate.split(b'    // For a 16-byte',1)[0].split(b') (',1)[1]
    fifo=[]
    for side in ['w','r']:
        folder=PROJECT/f'ipcore/ddr_fifo16_{side}'
        fifo += [folder/f'ddr_fifo16_{side}.v'] + sorted((folder/'rtl').glob('*.v'))
    dependencies = fifo + [ORIGINAL, CANDIDATE, Path(__file__).resolve(),
                           CONTRACT/'tb_ddr_adapter_contract.sv', CONTRACT/'fpga_v8_vendor_ddr_stub.sv',
                           CONTRACT/'fpga_v8_top_read_route_snapshot.v', PROJECT/'source/top.v',
                           V4/'evidence/all_reported_failing_paths.json', V4/'rtl/axi_dma_write_tc02.v']
    hashes={str(p.relative_to(PROJECT)).replace('\\','/'):sha(p) for p in dependencies}
    detail = json.loads((V4/'evidence/all_reported_failing_paths.json').read_bytes())
    path = next(p for p in detail if 'awlen_reg[5]' in p['Startpoint'])
    (ART/'v4_awlen_full_detail.txt').write_text(path['full_detail'],encoding='utf-8')
    totals=boundary_tb(); contract_tb()
    run([SIM/'vlib.exe','work'],ART,'vlib.log')
    run([SIM/'vlog.exe','-work','work',*fifo,ORIGINAL,CANDIDATE,
         CONTRACT/'fpga_v8_top_read_route_snapshot.v'],ART,'compile_rtl.log')
    run([SIM/'vlog.exe','-work','work','-sv',CONTRACT/'fpga_v8_vendor_ddr_stub.sv',
         ART/'tb_adapter_boundary.sv',ART/'tb_adapter_contract_diff.sv'],ART,'compile_tb.log')
    # ModelSim -onfinish stop treats successful $finish as a break too.
    # Fatal/Error text and mandatory PASS markers are checked separately.
    (ART/'run.do').write_text('onerror {quit -code 1}\nonbreak {quit -code 0}\nrun -all\nquit -code 0\n',encoding='ascii')
    runs=[]
    for top,marker in [('tb_adapter_boundary','ALL_BOUNDARY_PASS'),
                       ('tb_ddr_adapter_contract','RANDOM_TRANSACTION_PASS')]:
        text=run([SIM/'vsim.exe','-c','-onfinish','stop','-voptargs=+acc','-l',top+'.transcript.log',
                  'work.'+top,'-do','run.do'],ART,top+'.console.log')
        assert marker in text,text[-8000:]
        markers=[line.removeprefix('# ') for line in text.splitlines() if '_PASS' in line]
        runs.append(dict(top=top,markers=markers))
        print('\n'.join(markers),flush=True)
    assert hashes=={str(p.relative_to(PROJECT)).replace('\\','/'):sha(p) for p in dependencies}
    generated={p.name:sha(p) for p in ART.glob('*') if p.is_file() and p.suffix in ('.sv','.hex','.log','.txt','.do')}
    report=dict(status='PASS',seed=hex(SEED),python=sys.executable,modelsim=str(SIM),
                output_ports=[n for d,w,n in ports() if d=='output'],
                comparison='all public outputs, including invalid payloads, case inequality before/after clock and after stimulus',
                boundary_cases=totals,total_boundary_vectors=sum(c['vectors'] for c in totals),
                runs=runs,source_sha256=hashes,artifact_sha256=generated,
                dependency_hashes_unchanged=True,state_and_fifo_wiring_byte_equal=True,
                v4_path={k:v for k,v in path.items() if k!='full_detail'},
                limitations=['No PDS/synthesis/place-route run; timing gain unmeasured.',
                             'Actual unmodified generated FIFO RTL; DDR controller uses existing behavioral scheduling stub.',
                             'Finite deterministic two-state request stimuli; no formal proof or unknown-input equivalence claim.',
                             'Wide override values intentionally truncate to original 32-bit parameter semantics.'])
    (ART/'adapter_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='ascii')

if __name__=='__main__':
    main()
