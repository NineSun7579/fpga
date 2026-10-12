"""Isolated actual-source ModelSim regression. Writes only beneath this folder."""
from pathlib import Path
import hashlib, json, re, subprocess

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
FROZEN = HERE.parent / 'whole_candidate_v2_route_01' / 'inputs' / 'source'
SIM = Path(r'C:\modeltech64_10.6e\win64')
OUT = HERE / 'simulation'
OUT.mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(exe, args, log):
    proc = subprocess.run([str(SIM / exe), *args], cwd=OUT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT / log).write_bytes(proc.stdout)
    text = proc.stdout.decode(errors='replace')
    if proc.returncode or re.search(r'\*\* (?:Error|Fatal):', text):
        raise RuntimeError(f'{exe} failed: {log}\n{text[-5000:]}')
    return text

source_motion = FROZEN / 'motion/block_motion_detector.v'
source_decode = FROZEN / 'ov5640/ovreg_axil_decode.v'
source_tb = PROJECT / 'sim/motion/tb_block_motion_detector.sv'
protected = [source_motion, source_decode, source_tb]
before = {str(p): sha(p) for p in protected}

# Run the existing independent frame/history oracle against the new module,
# with an additional original-module instance checking every output every cycle.
tb = source_tb.read_bytes().decode('ascii')
tb = tb.replace('block_motion_detector #(', 'block_motion_detector_tc01 #(')
outputs = ['result_strobe','result_valid','bbox_valid','block_bitmap',
           'changed_blocks','changed_samples','bbox_min_x','bbox_max_x',
           'bbox_min_y','bbox_max_y','frame_sequence']
decl = '\n'.join(tb.splitlines()[13:20])
for n in sorted(outputs, key=len, reverse=True):
    decl = re.sub(r'\b'+n+r'\b', 'ref_'+n, decl)
ports = [f'.{n}(ref_{n})' for n in outputs]
ports += [f'.{n}({n})' for n in ['clk','rst_n','frame_start','frame_end','pixel_valid','pixel_rgb565']]
paired = decl + '''
    block_motion_detector #(.WIDTH(W),.HEIGHT(H),.SAMPLE_STEP(STEP),
        .BLOCK_SAMPLES_X(BSX),.BLOCK_SAMPLES_Y(BSY),
        .PIXEL_THRESHOLD(PTH),.BLOCK_THRESHOLD(BTH)) original (
        ''' + ','.join(ports) + ''');
    integer paired_cycles=0;
    always @(posedge clk) begin
        #2;
        if (rst_n) begin
            paired_cycles=paired_cycles+1;
            if ({''' + ','.join(outputs) + '} !== {' + ','.join('ref_'+n for n in outputs) + '''})
                $fatal(1,"TC01 original cycle mismatch W=%0d STEP=%0d cycle=%0d",W,STEP,paired_cycles);
        end
    end
'''
tb = tb.replace('    reg [15:0] image', paired+'\n    reg [15:0] image', 1)
(OUT / 'tb_motion_actual_paired.sv').write_text(tb, encoding='ascii')

# Discover every actual decoder port from its ANSI header, generate a paired
# external-interface checker. All output ports are checked; no hand-selected subset.
raw = source_decode.read_bytes().decode('ascii')
header = raw[raw.index(')(\n')+3:raw.index('\n);')]
header = re.sub(r'//[^\n]*', '', header)
portspec = re.findall(r'\b(input|output)\s*(\[[^\]]+\])?\s*(\w+)', header)
assert len(portspec) > 90, len(portspec)
inputs = [(w or '', n) for d,w,n in portspec if d=='input']
outs = [(w or '', n) for d,w,n in portspec if d=='output']
lines = ['`timescale 1ns/1ps', 'module decode_case #(parameter LSB=8)(output reg done=0);']
lines += [f'reg {w} {n}=0;' for w,n in inputs]
lines += [f'wire {w} old_{n}, new_{n};' for w,n in outs]
for typ,prefix in [('ovreg_axil_decode','old_'),('ovreg_axil_decode_tc01','new_')]:
    bindings = [f'.{n}({n})' for _,n in inputs] + [f'.{n}({prefix}{n})' for _,n in outs]
    lines += [f'{typ} #(.ADDR_SEL_LSB(LSB)) {prefix}dut ('+', '.join(bindings)+');']
lines += ['always #5 clk=~clk;', 'integer i,j,checks=0; reg [31:0] rng=32\'h31c0ffee;',
          'function [31:0] next_rng(input [31:0] r); begin next_rng={r[30:0],r[31]^r[21]^r[1]^r[0]}; end endfunction',
          'task check; begin #1; checks=checks+1;']
for _,n in outs:
    lines += [f'if (old_{n} !== new_{n}) $fatal(1,"decoder LSB=%0d {n} mismatch i=%0d AW=%h AR=%h",LSB,i,s_awaddr,s_araddr);']
lines += ['end endtask', 'task drive_random; begin']
for _,n in inputs:
    if n not in ('clk','rst','s_awaddr','s_araddr'):
        lines += [f'rng=next_rng(rng); {n}=rng;']
lines += ['end endtask','initial begin', 'rst=1; @(posedge clk); check(); @(negedge clk); rst=0;',
          # Exhaustive routing nibble plus exact motion, aliases and CDC offsets.
          'for (i=0;i<65536;i=i+1) begin', '@(negedge clk); drive_random();',
          'case ((i>>12)&7)',
          '0: begin s_awaddr=32\'h20000000+(i&4095); s_araddr=s_awaddr; end',
          '1: begin s_awaddr=32\'h20000800+(i&255); s_araddr=32\'h20000800+(i&255); end',
          '2: begin s_awaddr=32\'h20001800+(i&4095); s_araddr=s_awaddr; end',
          '3: begin s_awaddr=32\'h21000000+(i&4095); s_araddr=s_awaddr; end',
          '4: begin s_awaddr=32\'h20000000+((i&3)<<9)+32\'h190+(((i>>2)&3)<<4); s_araddr=s_awaddr; end',
          'default: begin rng=next_rng(rng); s_awaddr=rng; rng=next_rng(rng); s_araddr=rng; end',
          'endcase', 'rst=(i%997==0); check(); @(posedge clk); check();',
          'end', '$display("PASS decoder paired LSB=%0d checks=%0d",LSB,checks); done=1;', 'end', 'endmodule',
          'module tb_decode_paired; wire d8,d7,d9;',
          'decode_case #(.LSB(8)) a(d8); decode_case #(.LSB(7)) b(d7); decode_case #(.LSB(9)) c(d9);',
          'initial begin wait(d8 && d7 && d9); $display("PASS ALL decoder output-cycle comparisons"); $finish; end',
          'initial begin #2000000; $fatal(1,"decoder timeout"); end', 'endmodule']
(OUT / 'tb_decode_paired.sv').write_text('\n'.join(lines)+'\n', encoding='ascii')

run('vlib.exe', ['work'], 'vlib.log')
run('vlog.exe', ['-sv', '-work', 'work', str(source_motion), str(source_decode),
    str(HERE/'rtl/block_motion_detector_tc01.v'), str(HERE/'rtl/ovreg_axil_decode_tc01.v'),
    str(OUT/'tb_motion_actual_paired.sv'), str(OUT/'tb_decode_paired.sv')], 'compile.log')
def simulate(top, marker, log):
    text = run('vsim.exe', ['-c','-voptargs=+acc', 'work.'+top,
        '-do','onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'], log)
    if marker not in text:
        raise RuntimeError(f'Missing pass marker in {log}')
    return text
simulate('tb_block_motion_detector','PASS ALL block_motion_detector self-checks','motion.log')
simulate('tb_decode_paired','PASS ALL decoder output-cycle comparisons','decoder.log')
after = {str(p): sha(p) for p in protected}
assert before == after
result = {'status':'PASS','simulator':str(SIM), 'protected_sources':before,
          'candidate_sources':{str(p):sha(p) for p in sorted((HERE/'rtl').glob('*.v'))},
          'motion':'actual five-geometry oracle plus original output comparison on every active cycle',
          'decoder':'all outputs, 65536 stimuli per LSB=7,8,9, before/after each edge',
          'pds_invoked':False,'ssh_invoked':False}
(HERE/'regression_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
