"""Prepare isolated TC04 from frozen V5 bytes; never writes the reference."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parents[1]
PROJECT = HERE.parents[1]
REF = PROJECT / 'fpga_v8_migration/whole_candidate_v5_route_01/rtl/fpga_v8_capture_lease.v'


def candidate():
    text = REF.read_bytes().decode('ascii')
    text = text.replace('module fpga_v8_capture_lease #(', 'module fpga_v8_capture_lease_tc04 #(')
    text = text.replace('    integer i;', '''    // Exact redundant predicates of CURRENT state, computed from next state.
    // No external input is pipelined and no authorization is delayed.
    reg writing_eligible, next_nonzero, next_last;
    reg [1:0] state_d [0:1];
    reg writing_bank_d;
    wire publish_qualified = writing_eligible && next_nonzero &&
                             (~|(publish_seq ^ next_sequence));
    wire publish_success = publish && publish_qualified;
    wire config_success = config_valid && config_ready && PARAM_OK &&
        config_generation != 0 && config_generation != generation && !protocol_fault;
    integer k;
    always @* begin
        state_d[0] = state[0];
        state_d[1] = state[1];
        writing_bank_d = writing_bank;
        if (admitted_sof && !lease_block) begin
            state_d[capture_bank] = WRITING;
            writing_bank_d = capture_bank;
        end
        // Preserve original old-state evaluation and assignment priority.
        if (publish_success) state_d[writing_bank] = HELD;
        else if (!publish && retired_error && writing_eligible)
            state_d[writing_bank] = FREE;
        for (k=0; k<2; k=k+1)
            if (state[k] == HELD &&
                (coop_released[k] || (coop_fire && release_bank == k)) &&
                (host_released[k] || (host_fire && host_release_bank == k)))
                state_d[k] = FREE;
    end
    always @(posedge clk) begin
        if (rst) begin
            writing_eligible <= 0;
            next_nonzero <= 1;
            next_last <= 0;
        end else begin
            writing_eligible <= state_d[writing_bank_d] == WRITING;
            if (config_success) begin
                next_nonzero <= 1;
                next_last <= 0;
            end
            // Publication overrides configuration, exactly as in V5.
            if (publish_success) begin
                next_nonzero <= !next_last;
                next_last <= next_sequence == 32'hfffffffe;
            end
        end
    end
    // Four-bit local incrementers: late publication does not enter a 32-bit
    // increment ripple. Carry qualification depends only on registered count.
    genvar chunk;
    generate for (chunk=0; chunk<8; chunk=chunk+1) begin : published_chunks
        wire carry_in;
        if (chunk == 0) assign carry_in = publish_success;
        else assign carry_in = publish_success && (&published_count[chunk*4-1:0]);
        always @(posedge clk) begin
            if (rst) published_count[chunk*4 +: 4] <= 0;
            else published_count[chunk*4 +: 4] <=
                published_count[chunk*4 +: 4] + carry_in;
        end
    end endgenerate
    integer i;''')
    text = text.replace('            published_count <= 0;\n', '')
    text = text.replace('            writing_bank <= 0;', '            writing_bank <= 0;')
    text = text.replace('        end else begin\n            epoch_start <= 0;', '''        end else begin
            state[0] <= state_d[0];
            state[1] <= state_d[1];
            writing_bank <= writing_bank_d;
            epoch_start <= 0;''')
    text = text.replace('                    state[capture_bank] <= WRITING;\n                    writing_bank <= capture_bank;\n', '')
    text = text.replace('state[writing_bank] == WRITING && publish_seq == next_sequence && publish_seq != 0', 'publish_qualified')
    text = text.replace('                    state[writing_bank] <= HELD;\n', '')
    text = text.replace('sequence[writing_bank] <= publish_seq;', 'sequence[writing_bank] <= next_sequence;')
    text = text.replace('                    published_count <= published_count + 1\'b1;\n', '')
    text = text.replace("if (next_sequence == 32'hffffffff) armed <= 0;", 'if (next_last) armed <= 0;')
    text = text.replace('retired_error && state[writing_bank] == WRITING', 'retired_error && writing_eligible')
    text = text.replace('                state[writing_bank] <= FREE;\n', '')
    start = text.index('            for (i=0; i<2; i=i+1) begin', text.index('            if (coop_fire)'))
    end = text.index('            end\n', start) + len('            end\n')
    text = text[:start] + text[end:]
    return text.encode('ascii')


if __name__ == '__main__':
    # Emit a patch for the caller to apply with the patch tool.
    data = candidate().decode('ascii')
    print('*** Begin Patch\n*** Add File: project/fpga_v8_migration/timing_correction_04/rtl/fpga_v8_capture_lease_tc04.v')
    print('\n'.join('+' + line for line in data.splitlines()))
    print('*** End Patch')
