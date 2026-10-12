"""Isolated TC05 RTL equivalence and TC04 integration; never invokes PDS."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parents[1]
MIG = HERE.parent
PROJECT = MIG.parent
TC01 = MIG / 'timing_correction_01'
TC03 = MIG / 'timing_correction_03'
TC04 = MIG / 'timing_correction_04'
V6 = MIG / 'whole_candidate_v6_route_01'
CANDIDATE = HERE / 'rtl/block_motion_detector_tc05.v'
SIM = Path(os.environ.get('MODELSIM_BIN', r'C:\modeltech64_10.6e\win64'))
OUT = HERE / 'receipts' / ('detector_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
OUTPUTS = ['result_strobe', 'result_valid', 'bbox_valid', 'block_bitmap',
           'changed_blocks', 'changed_samples', 'bbox_min_x', 'bbox_max_x',
           'bbox_min_y', 'bbox_max_y', 'frame_sequence']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return p.read_bytes().decode('ascii')


def write(name, text):
    p = OUT / name
    p.write_bytes(text.encode('ascii'))
    return p


def run(exe, args, label, marker=None):
    proc = subprocess.run([str(SIM / exe), *map(str, args)], cwd=OUT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    (OUT / (label + '.log')).write_bytes(proc.stdout)
    text = proc.stdout.decode(errors='replace')
    if proc.returncode or re.search(r'\*\* (?:Error|Fatal):', text) or (marker and marker not in text):
        raise RuntimeError(label + '\n' + text[-9000:])
    print('PASS ' + label, flush=True)
    return text


def simulate(top, label, marker, params=()):
    return run('vsim.exe', ['-c', '-vopt', '-voptargs=+acc', 'work.' + top, *params,
               '-do', 'onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'],
               label, marker)


def monitor(dut, refs, ns='NS'):
    """Check every public output, same-edge memory transactions and eligibility."""
    body = f'''
    integer history_checks=0, history_writes=0, history_resets=0;
    integer history_index, written_address;
    reg did_write;
    always @(posedge clk) begin
        did_write={dut}.rst_n && {dut}.accept_sample;
        written_address={dut}.sample_address;
'''
    for ref in refs:
        body += f'''
        if ({{{dut}.rst_n && {dut}.accept_sample,{dut}.sample_address,{dut}.luma}} !==
            {{{ref}.rst_n && {ref}.accept_sample,{ref}.sample_address,{ref}.luma}})
            $fatal(1,"TC05 history transaction differs from {ref}");
'''
    body += f'''
        #2;
        history_checks=history_checks+1;
        if (!{dut}.rst_n) history_resets=history_resets+1;
        if ({dut}.history_eligible !== ({dut}.active &&
            {dut}.pixel_count<{dut}.TOTAL_PIXELS &&
            ({dut}.x%{dut}.SAMPLE_STEP)==0 && ({dut}.y%{dut}.SAMPLE_STEP)==0))
            $fatal(1,"TC05 lookahead invariant");
        if (did_write) history_writes=history_writes+1;
'''
    for ref in refs:
        lhs = ','.join(dut + '.' + n for n in OUTPUTS)
        rhs = ','.join(ref + '.' + n for n in OUTPUTS)
        body += f'''
        if ({{{lhs}}} !== {{{rhs}}})
            $fatal(1,"TC05 public output mismatch vs {ref}");
        if ({dut}.history_q !== {ref}.history_q)
            $fatal(1,"TC05 read-first history_q mismatch vs {ref}");
        if (did_write && {dut}.history[written_address] !== {ref}.history[written_address])
            $fatal(1,"TC05 written history byte mismatch vs {ref}");
        if ({dut}.frame_start || {dut}.frame_end || !{dut}.rst_n) begin
            for (history_index=0;history_index<{ns};history_index=history_index+1)
                if ({dut}.history[history_index] !== {ref}.history[history_index])
                    $fatal(1,"TC05 retained history mismatch vs {ref}");
        end
'''
    return body + '    end\n'


def main():
    OUT.mkdir(parents=True)
    protected = sorted({p for base in (PROJECT / 'source', PROJECT / 'ipcore',
                       TC01, TC03, TC04, V6 / 'rtl') for p in base.rglob('*')
                       if p.is_file() and p.suffix in ('.v', '.sv', '.py', '.pds', '.fdc')}
                       | {PROJECT / 'project.pds', PROJECT / 'sim/motion/tb_block_motion_detector.sv',
                          PROJECT / 'sim/motion/tb_four_motion.sv'})
    protected = [p for p in protected if p.is_file()]
    before = {str(p): sha(p) for p in protected}
    write('protected_before.json', json.dumps(before, indent=2) + '\n')
    candidate_sha = sha(CANDIDATE)
    # Byte-level module scan excludes frozen copies of existing candidates.
    declarations = [p for base in (PROJECT / 'source', HERE / 'rtl')
                    for p in base.rglob('*.v')
                    if re.search(rb'\bmodule\s+block_motion_detector_tc05\b', p.read_bytes())]
    assert declarations == [CANDIDATE], declarations
    assert (V6 / 'rtl/block_motion_detector_tc03.v').read_bytes() == (TC03 / 'rtl/block_motion_detector_tc03.v').read_bytes()
    paths = json.loads((V6 / 'evidence/all_reported_failing_paths.json').read_bytes())
    assert len(paths) == 1 and paths[0]['Slack'] == -0.037 and '/WEA[0]' in paths[0]['Endpoint']
    write('v6_failing_paths.json', json.dumps(paths, indent=2) + '\n')
    write('candidate.diff', ''.join(difflib.unified_diff(
        read(TC03 / 'rtl/block_motion_detector_tc03.v').splitlines(True),
        read(CANDIDATE).splitlines(True), fromfile='TC03', tofile='TC05')))
    # Use the existing independent frame/history/literal oracle generator prefix.
    prefix = read(TC01 / 'run_regression.py').split('# Discover every actual decoder port', 1)[0]
    prefix = prefix.replace('HERE = Path(__file__).resolve().parent', 'HERE = TC05')
    prefix = prefix.replace("OUT = HERE / 'simulation'", 'OUT = RUN_OUT')
    prefix = prefix.replace('block_motion_detector_tc01', 'block_motion_detector_tc05')
    env = {'__file__': str(TC01 / 'run_regression.py'), 'TC05': HERE, 'RUN_OUT': OUT}
    exec(compile(prefix, 'TC01-motion-oracle-prefix', 'exec'), env)
    tb = env['tb']
    refs = ['original']
    for tag, module in [('tc01', 'block_motion_detector_tc01'), ('tc03', 'block_motion_detector_tc03')]:
        paired = env['paired'].replace('ref_', tag + '_').replace('paired_cycles', tag + '_cycles')
        paired = paired.replace('block_motion_detector #(', module + ' #(')
        paired = paired.replace(' original (', ' ' + tag + '_original (')
        tb = tb.replace('    reg [15:0] image', paired + '\n    reg [15:0] image', 1)
        refs.append(tag + '_original')
    tb = tb.replace('    reg [15:0] image', monitor('dut', refs) + '\n    reg [15:0] image', 1)
    tb = tb.replace('        done=1;', '''        #3;
        $display("TC05_PAIRED W=%0d H=%0d STEP=%0d checks=%0d writes=%0d resets=%0d",W,H,STEP,history_checks,history_writes,history_resets);
        done=1;''')
    paired_tb = write('tb_motion_actual_paired.sv', tb)
    # Additional arbitrary marker combinations, async resets and nonpower-of-two steps.
    stress = tb.split('    reg [15:0] image', 1)[0].replace('module motion_case', 'module stress_case')
    stress += '''
    reg [31:0] rng=32'h5c050001+W*17+H*3+STEP;
    function [31:0] random_word;
        begin rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5); random_word=rng; end
    endfunction
    task drive(input bit fs, fe, pv, input [15:0] color);
        begin @(negedge clk); frame_start=fs; frame_end=fe; pixel_valid=pv; pixel_rgb565=color;
            @(posedge clk); #3; end
    endtask
    integer k,j,f; reg [31:0] r;
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        // Dense consecutive samples, row transitions, exact limit and excess tails.
        for(f=0;f<4;f=f+1) begin
            drive(1,f[0],1,16'hdead);
            for(j=0;j<W*H;j=j+1) begin
                r=random_word(); if(f[1] && r[1:0]==0) drive(0,0,0,16'hffff);
                drive(0,0,1,r[15:0]);
            end
            repeat(3) drive(0,0,1,16'hbeef);
            drive(0,1,1,16'hffff); drive(1,0,1,16'hdead);
        end
        // Reset at every position near accepted samples/end/publication.
        for(k=0;k<8;k=k+1) begin
            drive(1,0,1,0);
            for(j=0;j<W*H;j=j+1) drive(0,0,1,j);
            drive(0,1,1,0);
            for(j=0;j<k;j=j+1) drive(0,0,1,j);
            @(negedge clk); #1; rst_n=0; #1;
            if(dut.history_eligible!==0 || dut.result_strobe!==0) $fatal(1,"async reset");
            drive(1,1,1,16'hffff); @(negedge clk); #1; rst_n=1;
        end
        for(k=0;k<24000;k=k+1) begin
            r=random_word();
            // Exhaust every marker/valid combination, then mostly pixels with sparse markers.
            if(k%64<8) drive(k[2],k[1],k[0],r[15:0]);
            else drive(r[12:8]==0,r[17:13]==0,r[0],r[31:16]);
            if(k%997==0) begin @(negedge clk); #1; rst_n=0; #1; @(negedge clk); #1; rst_n=1; end
        end
        #3; $display("TC05_STRESS W=%0d H=%0d STEP=%0d checks=%0d writes=%0d resets=%0d",W,H,STEP,history_checks,history_writes,history_resets);
        done=1;
    end
endmodule
module tb_stress;
    wire [7:0] done;
    stress_case #(.W(5),.H(3),.STEP(1)) a(done[0]);
    stress_case #(.W(1),.H(1),.STEP(1),.BSX(1),.BSY(1),.BTH(1)) b(done[1]);
    stress_case #(.W(7),.H(5),.STEP(3)) c(done[2]);
    stress_case #(.W(1),.H(7),.STEP(2)) d(done[3]);
    stress_case #(.W(9),.H(1),.STEP(2)) e(done[4]);
    stress_case #(.W(3),.H(2),.STEP(5)) f(done[5]);
    stress_case #(.W(16),.H(8),.STEP(4)) g(done[6]);
    stress_case #(.W(17),.H(11),.STEP(3),.BTH(1)) h(done[7]);
    initial begin wait(&done); $display("PASS TC05 STRESS ALL"); $finish; end
    initial begin #10000000; $fatal(1,"stress timeout"); end
endmodule
'''
    stress_tb = write('tb_stress.sv', stress)
    # Test-only TC04 clone: sole behavior change is detector binding/module name.
    adapter = read(TC04 / 'rtl/motion_stream_adapter_tc04.v')
    adapter = adapter.replace('motion_stream_adapter_tc04', 'motion_stream_adapter_tc05_test')
    adapter = adapter.replace('block_motion_detector_tc03', 'block_motion_detector_tc05')
    bound_adapter = write('motion_stream_adapter_tc05_test.v', adapter)
    integ = read(TC04 / 'tb_motion_tc04.sv')
    integ = integ.replace('motion_stream_adapter_tc04 #(', 'motion_stream_adapter_tc05_test #(')
    integ = integ.replace('motion_stream_adapter #(', 'motion_stream_adapter_tc04 #(')
    integ = integ.replace('tb_motion_tc04', 'tb_motion_tc05')
    integ = integ.replace('    integer comparisons=0',
        '    localparam NS=((W+3)/4)*((H+3)/4);\n' +
        monitor('dut.u_detector', ['ref_dut.u_detector']) + '    integer comparisons=0')
    integration_tb = write('tb_motion_tc05.sv', integ)
    four = (PROJECT / 'sim/motion/tb_four_motion.sv').read_bytes().decode('ascii')
    assert 'motion_stream_adapter adapter' in four
    four_tb = write('tb_four_motion_tc05.sv', four.replace('motion_stream_adapter adapter',
                                                       'motion_stream_adapter_tc05_test adapter'))
    register = V6 / 'inputs/source/motion/motion_register_bank.v'
    sources = [env['source_motion'], TC01 / 'rtl/block_motion_detector_tc01.v',
               TC03 / 'rtl/block_motion_detector_tc03.v', CANDIDATE,
               TC04 / 'rtl/motion_stream_adapter_tc04.v', bound_adapter,
               paired_tb, stress_tb, integration_tb, register, four_tb]
    inputs = {str(p): sha(p) for p in sources + [Path(__file__).resolve()]}
    write('compile_sources.json', json.dumps(inputs, indent=2) + '\n')
    run('vlib.exe', ['work'], 'vlib')
    run('vlog.exe', ['-sv', '-work', 'work', *sources], 'compile')
    logs = {}
    logs['paired'] = simulate('tb_block_motion_detector', 'paired', 'PASS ALL block_motion_detector self-checks')
    assert len(re.findall('TC05_PAIRED W=', logs['paired'])) == 5
    logs['stress'] = simulate('tb_stress', 'stress', 'PASS TC05 STRESS ALL')
    assert len(re.findall('TC05_STRESS W=', logs['stress'])) == 8
    for w,h,seed in [(640,480,1), (640,480,29), (64,48,202603)]:
        label = f'integration_{w}_{h}_{seed}'
        logs[label] = simulate('tb_motion_tc05', label, 'MOTION_TC04_PASS',
                              [f'-gW={w}', f'-gH={h}', f'-gSEED={seed}'])
    logs['four'] = simulate('tb_four_motion', 'four', 'PASS')
    assert all(sha(Path(p)) == value for p,value in before.items()), 'protected file changed'
    assert all(sha(Path(p)) == value for p,value in inputs.items()), 'test input changed'
    assert sha(CANDIDATE) == candidate_sha
    metrics = {name: re.findall(r'(?:TC05_PAIRED|TC05_STRESS|MOTION_TC04_PASS|PASS)[^\r\n]*', text)
               for name,text in logs.items()}
    result = {'status': 'PASS', 'candidate': str(CANDIDATE), 'candidate_sha256': candidate_sha,
              'simulator': str(SIM), 'compile_sources': inputs, 'metrics': metrics,
              'oracle': 'TC01 independent frame/history/literal oracle, five geometries including packed 640x480',
              'equivalence': 'All 11 outputs every cycle including reset vs original/TC01/TC03; same-edge history enable/address/luma, read-first data, written bytes, full history at markers/reset',
              'stress': '8 geometries; nonpower-of-two SAMPLE_STEP, STEP=1, all 8 marker/valid combinations, asynchronous resets, tails, stalls and boundary restarts',
              'integration': 'TC04 paired adapters with TC03 vs TC05 detectors, 3 cases; full-resolution four-stream atomic record oracle',
              'protected_files_verified': len(before), 'protected_hashes_unchanged': True,
              'pds_invoked': False, 'flashing_invoked': False, 'physical_timing_verified': False,
              'resource_intent': 'Same 19200x8 read-first history per default detector; four default detectors intend unchanged 32 DRM, requires main synthesis confirmation',
              'limitations': 'RTL simulation is not formal proof. New eligibility-D path and fanout/routing need whole-design STA; DRM inference/resource count not measured here.'}
    result['artifacts'] = {str(p.relative_to(OUT)): sha(p) for p in OUT.iterdir()
                           if p.is_file() and p.suffix in ('.sv', '.v', '.log', '.json', '.diff')}
    write('results.json', json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'candidate_sha256': candidate_sha, 'receipts': str(OUT),
                      'protected_files_verified': len(before)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
