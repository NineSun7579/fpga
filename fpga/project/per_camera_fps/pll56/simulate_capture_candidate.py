"""Private ModelSim full-frame policy regression plus cycle-exact comparison."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE / 'build_aai6kbmf/inputs/source/motion'
CAND = HERE / 'capture_candidate'
SIM = ROOT / 'project/sim/motion'
BIN = Path('C:/modeltech64_10.6e/win64')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    work = Path(tempfile.mkdtemp(prefix='sim_capture_', dir=HERE))
    original = BASE / 'motion_stream_adapter.v'
    raw = original.read_bytes()
    assert raw.count(b'module motion_stream_adapter #(') == 1
    renamed = work / 'original_adapter.v'
    renamed.write_bytes(raw.replace(b'module motion_stream_adapter #(', b'module original_adapter #('))
    tb = (SIM / 'tb_motion_stream_adapter.sv').read_bytes()
    addition = b'''
    wire [319:0] ref_record, ref_full, ref_tiny;
    original_adapter #(.WIDTH(8), .HEIGHT(8), .SAMPLE_STEP(1),
        .BLOCK_SAMPLES_X(2), .BLOCK_SAMPLES_Y(2), .BLOCK_THRESHOLD(2)) ref_small (
        .clk(clk),.rst_n(rst_n),.pixel_rgb565(pix),.pixel_valid(valid),.vsync(vs),.motion_record(ref_record));
    original_adapter #(.WIDTH(11'd640), .HEIGHT(11'd480)) ref_big (
        .clk(clk),.rst_n(rst_n),.pixel_rgb565(full_pix),.pixel_valid(full_valid),.vsync(full_vs),.motion_record(ref_full));
    original_adapter #(.WIDTH(2), .HEIGHT(2), .SAMPLE_STEP(1),
        .BLOCK_SAMPLES_X(1), .BLOCK_SAMPLES_Y(1), .BLOCK_THRESHOLD(1)) ref_fault (
        .clk(clk),.rst_n(rst_n && tiny_link_ready),.pixel_rgb565(tiny_pix),
        .pixel_valid(tiny_valid),.vsync(tiny_vs),.motion_record(ref_tiny));
    integer equivalence_edges=0;
    always @(posedge clk) begin
        #1;
        if (record !== ref_record || full_record !== ref_full || tiny_record !== ref_tiny)
            $fatal(1,"cycle-exact original/candidate record mismatch");
        if ({dut.source_sequence,dut.overflow_count,dut.short_frame_count,dut.queued,
             full_dut.source_sequence,full_dut.overflow_count,full_dut.queued,
             tiny.source_sequence,tiny.overflow_count,tiny.short_frame_count,tiny.queued} !==
            {ref_small.source_sequence,ref_small.overflow_count,ref_small.short_frame_count,ref_small.queued,
             ref_big.source_sequence,ref_big.overflow_count,ref_big.queued,
             ref_fault.source_sequence,ref_fault.overflow_count,ref_fault.short_frame_count,ref_fault.queued})
            $fatal(1,"cycle-exact control/diagnostic mismatch");
        equivalence_edges=equivalence_edges+1;
    end
'''
    assert tb.count(b'endmodule') == 1
    tb = tb.replace(b'endmodule', addition + b'endmodule')
    tb = tb.replace(b'$display("PASS tb_motion_stream_adapter");',
                    b'$display("PASS CAPTURE_EQUIVALENCE edges=%0d",equivalence_edges);\n        $display("PASS tb_motion_stream_adapter");')
    test = work / 'tb_adapter_equivalence.sv'
    test.write_bytes(tb)
    commands = [
        [BIN/'vlib.exe', 'work'],
        [BIN/'vlog.exe','-sv', BASE/'block_motion_detector.v', CAND/'motion_stream_adapter.v', renamed, test],
        [BIN/'vsim.exe','-c','work.tb_motion_stream_adapter','-do',
         'onerror {quit -code 1 -force}; onbreak {quit -code 1 -force}; run -all; quit -code 0 -force']]
    log = work / 'simulation.log'
    with log.open('wb') as stream:
        for cmd in commands:
            print('SIM_STAGE',cmd[0].name,work,flush=True)
            result = subprocess.run([str(x) for x in cmd], cwd=work, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=180)
            stream.write(result.stdout); stream.flush()
            if result.returncode: raise RuntimeError('ModelSim failed: '+str(log))
    output = log.read_bytes()
    assert b'PASS CAPTURE_EQUIVALENCE' in output and b'PASS tb_motion_stream_adapter' in output
    assert b'** Error' not in output and b'** Fatal' not in output
    receipt = dict(status='PASS', candidate_sha256=sha(CAND/'motion_stream_adapter.v'),
                   original_sha256=sha(original), detector_sha256=sha(BASE/'block_motion_detector.v'),
                   testbench_sha256=sha(test), log_sha256=sha(log), work=str(work),
                   scope='Cycle-exact original/candidate comparison; full 640x480, continuous/gapped pixels, dummy/tails, abort, overflow, link-reset and five-clock blanking policies')
    (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS CAPTURE_SIMULATION',work/'receipt.json',flush=True)

if __name__ == '__main__':
    main()
