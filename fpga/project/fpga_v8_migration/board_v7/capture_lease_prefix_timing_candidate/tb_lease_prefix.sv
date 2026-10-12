`timescale 1ns/1ps
module tb_lease_tc04;
parameter HOST_REQUIRED=1, BAD_CFG=0;
localparam VALID_CFG=(BAD_CFG==0);
reg clk=0; always #5 clk=~clk;
reg rst=0;
reg config_valid=0;
wire ref_config_ready, dut_config_ready;
reg [31:0] config_generation=0;
wire ref_config_accept, dut_config_accept;
wire ref_config_reject, dut_config_reject;
wire ref_epoch_start, dut_epoch_start;
wire ref_armed, dut_armed;
wire ref_config_ok, dut_config_ok;
reg engine_idle=0;
reg capture_bank=0;
reg admitted_sof=0;
reg publish=0;
reg [31:0] publish_seq=0;
reg retired_error=0;
wire ref_lease_block, dut_lease_block;
wire [1:0] ref_bank0_state, dut_bank0_state;
wire [1:0] ref_bank1_state, dut_bank1_state;
wire ref_protocol_fault, dut_protocol_fault;
wire ref_input_valid, dut_input_valid;
reg input_ready=0;
wire ref_input_raw_valid, dut_input_raw_valid;
wire [31:0] ref_input_src_addr, dut_input_src_addr;
wire [31:0] ref_input_length, dut_input_length;
wire [31:0] ref_input_seq, dut_input_seq;
wire [31:0] ref_input_generation, dut_input_generation;
wire [2:0] ref_input_camera, dut_input_camera;
wire ref_input_bank, dut_input_bank;
wire [63:0] ref_input_token, dut_input_token;
reg release_valid=0;
wire ref_release_ready, dut_release_ready;
reg [2:0] release_camera=0;
reg release_bank=0;
reg [31:0] release_seq=0;
reg [31:0] release_generation=0;
reg [63:0] release_token=0;
wire ref_release_accept, dut_release_accept;
wire ref_release_reject, dut_release_reject;
wire ref_host_valid, dut_host_valid;
reg host_ready=0;
wire [31:0] ref_host_src_addr, dut_host_src_addr;
wire [31:0] ref_host_length, dut_host_length;
wire [31:0] ref_host_seq, dut_host_seq;
wire [31:0] ref_host_generation, dut_host_generation;
wire [2:0] ref_host_camera, dut_host_camera;
wire ref_host_bank, dut_host_bank;
wire [63:0] ref_host_token, dut_host_token;
reg host_release_valid=0;
wire ref_host_release_ready, dut_host_release_ready;
reg [2:0] host_release_camera=0;
reg host_release_bank=0;
reg [31:0] host_release_seq=0;
reg [31:0] host_release_generation=0;
reg [63:0] host_release_token=0;
wire ref_host_release_accept, dut_host_release_accept;
wire ref_host_release_reject, dut_host_release_reject;
wire [31:0] ref_published_count, dut_published_count;
wire [31:0] ref_failed_count, dut_failed_count;
wire [31:0] ref_rejected_release_count, dut_rejected_release_count;
fpga_v8_capture_lease_tc04 #(.HOST_REQUIRED(HOST_REQUIRED),
        .BANK1_ADDR(BAD_CFG==1 ? 32'h01800010 : BAD_CFG==2 ? 32'h0ffff000 :
                    BAD_CFG==3 ? 32'h01a00001 : 32'h01a00000),
        .CAM_DATA_LEN(BAD_CFG==4 ? 38401 : 38400),
        .DATA_WIDTH(BAD_CFG==5 ? 24 : 16),
        .RAW_LENGTH(BAD_CFG==6 ? 614384 : 614400),
        .CAM_ID(BAD_CFG==7 ? 6 : 4)) reference (
.clk(clk),
.rst(rst),
.config_valid(config_valid),
.config_ready(ref_config_ready),
.config_generation(config_generation),
.config_accept(ref_config_accept),
.config_reject(ref_config_reject),
.epoch_start(ref_epoch_start),
.armed(ref_armed),
.config_ok(ref_config_ok),
.engine_idle(engine_idle),
.capture_bank(capture_bank),
.admitted_sof(admitted_sof),
.publish(publish),
.publish_seq(publish_seq),
.retired_error(retired_error),
.lease_block(ref_lease_block),
.bank0_state(ref_bank0_state),
.bank1_state(ref_bank1_state),
.protocol_fault(ref_protocol_fault),
.input_valid(ref_input_valid),
.input_ready(input_ready),
.input_raw_valid(ref_input_raw_valid),
.input_src_addr(ref_input_src_addr),
.input_length(ref_input_length),
.input_seq(ref_input_seq),
.input_generation(ref_input_generation),
.input_camera(ref_input_camera),
.input_bank(ref_input_bank),
.input_token(ref_input_token),
.release_valid(release_valid),
.release_ready(ref_release_ready),
.release_camera(release_camera),
.release_bank(release_bank),
.release_seq(release_seq),
.release_generation(release_generation),
.release_token(release_token),
.release_accept(ref_release_accept),
.release_reject(ref_release_reject),
.host_valid(ref_host_valid),
.host_ready(host_ready),
.host_src_addr(ref_host_src_addr),
.host_length(ref_host_length),
.host_seq(ref_host_seq),
.host_generation(ref_host_generation),
.host_camera(ref_host_camera),
.host_bank(ref_host_bank),
.host_token(ref_host_token),
.host_release_valid(host_release_valid),
.host_release_ready(ref_host_release_ready),
.host_release_camera(host_release_camera),
.host_release_bank(host_release_bank),
.host_release_seq(host_release_seq),
.host_release_generation(host_release_generation),
.host_release_token(host_release_token),
.host_release_accept(ref_host_release_accept),
.host_release_reject(ref_host_release_reject),
.published_count(ref_published_count),
.failed_count(ref_failed_count),
.rejected_release_count(ref_rejected_release_count)
);
fpga_v8_capture_lease_prefix #(.HOST_REQUIRED(HOST_REQUIRED),
        .BANK1_ADDR(BAD_CFG==1 ? 32'h01800010 : BAD_CFG==2 ? 32'h0ffff000 :
                    BAD_CFG==3 ? 32'h01a00001 : 32'h01a00000),
        .CAM_DATA_LEN(BAD_CFG==4 ? 38401 : 38400),
        .DATA_WIDTH(BAD_CFG==5 ? 24 : 16),
        .RAW_LENGTH(BAD_CFG==6 ? 614384 : 614400),
        .CAM_ID(BAD_CFG==7 ? 6 : 4)) dut (
.clk(clk),
.rst(rst),
.config_valid(config_valid),
.config_ready(dut_config_ready),
.config_generation(config_generation),
.config_accept(dut_config_accept),
.config_reject(dut_config_reject),
.epoch_start(dut_epoch_start),
.armed(dut_armed),
.config_ok(dut_config_ok),
.engine_idle(engine_idle),
.capture_bank(capture_bank),
.admitted_sof(admitted_sof),
.publish(publish),
.publish_seq(publish_seq),
.retired_error(retired_error),
.lease_block(dut_lease_block),
.bank0_state(dut_bank0_state),
.bank1_state(dut_bank1_state),
.protocol_fault(dut_protocol_fault),
.input_valid(dut_input_valid),
.input_ready(input_ready),
.input_raw_valid(dut_input_raw_valid),
.input_src_addr(dut_input_src_addr),
.input_length(dut_input_length),
.input_seq(dut_input_seq),
.input_generation(dut_input_generation),
.input_camera(dut_input_camera),
.input_bank(dut_input_bank),
.input_token(dut_input_token),
.release_valid(release_valid),
.release_ready(dut_release_ready),
.release_camera(release_camera),
.release_bank(release_bank),
.release_seq(release_seq),
.release_generation(release_generation),
.release_token(release_token),
.release_accept(dut_release_accept),
.release_reject(dut_release_reject),
.host_valid(dut_host_valid),
.host_ready(host_ready),
.host_src_addr(dut_host_src_addr),
.host_length(dut_host_length),
.host_seq(dut_host_seq),
.host_generation(dut_host_generation),
.host_camera(dut_host_camera),
.host_bank(dut_host_bank),
.host_token(dut_host_token),
.host_release_valid(host_release_valid),
.host_release_ready(dut_host_release_ready),
.host_release_camera(host_release_camera),
.host_release_bank(host_release_bank),
.host_release_seq(host_release_seq),
.host_release_generation(host_release_generation),
.host_release_token(host_release_token),
.host_release_accept(dut_host_release_accept),
.host_release_reject(dut_host_release_reject),
.published_count(dut_published_count),
.failed_count(dut_failed_count),
.rejected_release_count(dut_rejected_release_count)
);
task compare_outputs; begin
if(ref_config_ready !== dut_config_ready) $fatal(1,"output config_ready cycle=%0d ref=%h dut=%h",cycles,ref_config_ready,dut_config_ready);
if(ref_config_accept !== dut_config_accept) $fatal(1,"output config_accept cycle=%0d ref=%h dut=%h",cycles,ref_config_accept,dut_config_accept);
if(ref_config_reject !== dut_config_reject) $fatal(1,"output config_reject cycle=%0d ref=%h dut=%h",cycles,ref_config_reject,dut_config_reject);
if(ref_epoch_start !== dut_epoch_start) $fatal(1,"output epoch_start cycle=%0d ref=%h dut=%h",cycles,ref_epoch_start,dut_epoch_start);
if(ref_armed !== dut_armed) $fatal(1,"output armed cycle=%0d ref=%h dut=%h",cycles,ref_armed,dut_armed);
if(ref_config_ok !== dut_config_ok) $fatal(1,"output config_ok cycle=%0d ref=%h dut=%h",cycles,ref_config_ok,dut_config_ok);
if(ref_lease_block !== dut_lease_block) $fatal(1,"output lease_block cycle=%0d ref=%h dut=%h",cycles,ref_lease_block,dut_lease_block);
if(ref_bank0_state !== dut_bank0_state) $fatal(1,"output bank0_state cycle=%0d ref=%h dut=%h",cycles,ref_bank0_state,dut_bank0_state);
if(ref_bank1_state !== dut_bank1_state) $fatal(1,"output bank1_state cycle=%0d ref=%h dut=%h",cycles,ref_bank1_state,dut_bank1_state);
if(ref_protocol_fault !== dut_protocol_fault) $fatal(1,"output protocol_fault cycle=%0d ref=%h dut=%h",cycles,ref_protocol_fault,dut_protocol_fault);
if(ref_input_valid !== dut_input_valid) $fatal(1,"output input_valid cycle=%0d ref=%h dut=%h",cycles,ref_input_valid,dut_input_valid);
if(ref_input_raw_valid !== dut_input_raw_valid) $fatal(1,"output input_raw_valid cycle=%0d ref=%h dut=%h",cycles,ref_input_raw_valid,dut_input_raw_valid);
if(ref_input_src_addr !== dut_input_src_addr) $fatal(1,"output input_src_addr cycle=%0d ref=%h dut=%h",cycles,ref_input_src_addr,dut_input_src_addr);
if(ref_input_length !== dut_input_length) $fatal(1,"output input_length cycle=%0d ref=%h dut=%h",cycles,ref_input_length,dut_input_length);
if(ref_input_seq !== dut_input_seq) $fatal(1,"output input_seq cycle=%0d ref=%h dut=%h",cycles,ref_input_seq,dut_input_seq);
if(ref_input_generation !== dut_input_generation) $fatal(1,"output input_generation cycle=%0d ref=%h dut=%h",cycles,ref_input_generation,dut_input_generation);
if(ref_input_camera !== dut_input_camera) $fatal(1,"output input_camera cycle=%0d ref=%h dut=%h",cycles,ref_input_camera,dut_input_camera);
if(ref_input_bank !== dut_input_bank) $fatal(1,"output input_bank cycle=%0d ref=%h dut=%h",cycles,ref_input_bank,dut_input_bank);
if(ref_input_token !== dut_input_token) $fatal(1,"output input_token cycle=%0d ref=%h dut=%h",cycles,ref_input_token,dut_input_token);
if(ref_release_ready !== dut_release_ready) $fatal(1,"output release_ready cycle=%0d ref=%h dut=%h",cycles,ref_release_ready,dut_release_ready);
if(ref_release_accept !== dut_release_accept) $fatal(1,"output release_accept cycle=%0d ref=%h dut=%h",cycles,ref_release_accept,dut_release_accept);
if(ref_release_reject !== dut_release_reject) $fatal(1,"output release_reject cycle=%0d ref=%h dut=%h",cycles,ref_release_reject,dut_release_reject);
if(ref_host_valid !== dut_host_valid) $fatal(1,"output host_valid cycle=%0d ref=%h dut=%h",cycles,ref_host_valid,dut_host_valid);
if(ref_host_src_addr !== dut_host_src_addr) $fatal(1,"output host_src_addr cycle=%0d ref=%h dut=%h",cycles,ref_host_src_addr,dut_host_src_addr);
if(ref_host_length !== dut_host_length) $fatal(1,"output host_length cycle=%0d ref=%h dut=%h",cycles,ref_host_length,dut_host_length);
if(ref_host_seq !== dut_host_seq) $fatal(1,"output host_seq cycle=%0d ref=%h dut=%h",cycles,ref_host_seq,dut_host_seq);
if(ref_host_generation !== dut_host_generation) $fatal(1,"output host_generation cycle=%0d ref=%h dut=%h",cycles,ref_host_generation,dut_host_generation);
if(ref_host_camera !== dut_host_camera) $fatal(1,"output host_camera cycle=%0d ref=%h dut=%h",cycles,ref_host_camera,dut_host_camera);
if(ref_host_bank !== dut_host_bank) $fatal(1,"output host_bank cycle=%0d ref=%h dut=%h",cycles,ref_host_bank,dut_host_bank);
if(ref_host_token !== dut_host_token) $fatal(1,"output host_token cycle=%0d ref=%h dut=%h",cycles,ref_host_token,dut_host_token);
if(ref_host_release_ready !== dut_host_release_ready) $fatal(1,"output host_release_ready cycle=%0d ref=%h dut=%h",cycles,ref_host_release_ready,dut_host_release_ready);
if(ref_host_release_accept !== dut_host_release_accept) $fatal(1,"output host_release_accept cycle=%0d ref=%h dut=%h",cycles,ref_host_release_accept,dut_host_release_accept);
if(ref_host_release_reject !== dut_host_release_reject) $fatal(1,"output host_release_reject cycle=%0d ref=%h dut=%h",cycles,ref_host_release_reject,dut_host_release_reject);
if(ref_published_count !== dut_published_count) $fatal(1,"output published_count cycle=%0d ref=%h dut=%h",cycles,ref_published_count,dut_published_count);
if(ref_failed_count !== dut_failed_count) $fatal(1,"output failed_count cycle=%0d ref=%h dut=%h",cycles,ref_failed_count,dut_failed_count);
if(ref_rejected_release_count !== dut_rejected_release_count) $fatal(1,"output rejected_release_count cycle=%0d ref=%h dut=%h",cycles,ref_rejected_release_count,dut_rejected_release_count);
if(!rst && (dut.writing_eligible !== (dut.state[dut.writing_bank]==1) ||
dut.next_nonzero !== (dut.next_sequence!=0) ||
dut.next_last !== (dut.next_sequence==32'hffffffff))) $fatal(1,"predicate invariant");
if(reference.generation !== dut.generation) $fatal(1,"state generation cycle=%0d",cycles);
if(reference.next_sequence !== dut.next_sequence) $fatal(1,"state next_sequence cycle=%0d",cycles);
if(reference.writing_bank !== dut.writing_bank) $fatal(1,"state writing_bank cycle=%0d",cycles);
if(reference.coop_offer_bank !== dut.coop_offer_bank) $fatal(1,"state coop_offer_bank cycle=%0d",cycles);
if(reference.host_offer_bank !== dut.host_offer_bank) $fatal(1,"state host_offer_bank cycle=%0d",cycles);
if(reference.coop_rr !== dut.coop_rr) $fatal(1,"state coop_rr cycle=%0d",cycles);
if(reference.host_rr !== dut.host_rr) $fatal(1,"state host_rr cycle=%0d",cycles);
if(reference.writing_eligible !== dut.writing_eligible) $fatal(1,"state writing_eligible cycle=%0d",cycles);
if(reference.next_nonzero !== dut.next_nonzero) $fatal(1,"state next_nonzero cycle=%0d",cycles);
if(reference.next_last !== dut.next_last) $fatal(1,"state next_last cycle=%0d",cycles);
if(reference.state[0] !== dut.state[0]) $fatal(1,"state state[0] cycle=%0d",cycles);
if(reference.state[1] !== dut.state[1]) $fatal(1,"state state[1] cycle=%0d",cycles);
if(reference.\sequence [0] !== dut.\sequence [0]) $fatal(1,"state sequence[0] cycle=%0d",cycles);
if(reference.\sequence [1] !== dut.\sequence [1]) $fatal(1,"state sequence[1] cycle=%0d",cycles);
if(reference.coop_claimed[0] !== dut.coop_claimed[0]) $fatal(1,"state coop_claimed[0] cycle=%0d",cycles);
if(reference.coop_claimed[1] !== dut.coop_claimed[1]) $fatal(1,"state coop_claimed[1] cycle=%0d",cycles);
if(reference.coop_released[0] !== dut.coop_released[0]) $fatal(1,"state coop_released[0] cycle=%0d",cycles);
if(reference.coop_released[1] !== dut.coop_released[1]) $fatal(1,"state coop_released[1] cycle=%0d",cycles);
if(reference.host_claimed[0] !== dut.host_claimed[0]) $fatal(1,"state host_claimed[0] cycle=%0d",cycles);
if(reference.host_claimed[1] !== dut.host_claimed[1]) $fatal(1,"state host_claimed[1] cycle=%0d",cycles);
if(reference.host_released[0] !== dut.host_released[0]) $fatal(1,"state host_released[0] cycle=%0d",cycles);
if(reference.host_released[1] !== dut.host_released[1]) $fatal(1,"state host_released[1] cycle=%0d",cycles);
if(dut.published_prefix[1] !== (&dut.published_count[3:0])) $fatal(1,"prefix invariant width=4 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[2] !== (&dut.published_count[7:0])) $fatal(1,"prefix invariant width=8 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[3] !== (&dut.published_count[11:0])) $fatal(1,"prefix invariant width=12 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[4] !== (&dut.published_count[15:0])) $fatal(1,"prefix invariant width=16 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[5] !== (&dut.published_count[19:0])) $fatal(1,"prefix invariant width=20 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[6] !== (&dut.published_count[23:0])) $fatal(1,"prefix invariant width=24 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
if(dut.published_prefix[7] !== (&dut.published_count[27:0])) $fatal(1,"prefix invariant width=28 cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);
end endtask
integer cycles=0, seed=32'h40851, n, mask, b;
integer pubs=0, errors=0, coop_accepts=0, host_accepts=0, faults=0;
reg [31:0] r;
task tick;
begin
    #1; compare_outputs;
    if(!rst && publish && reference.state[reference.writing_bank]==1 &&
       publish_seq==reference.next_sequence && publish_seq!=0) pubs=pubs+1;
    if(!rst && !publish && retired_error && reference.state[reference.writing_bank]==1)
        errors=errors+1;
    @(posedge clk); #1; compare_outputs;
    cycles=cycles+1;
    if(ref_release_accept) coop_accepts=coop_accepts+1;
    if(ref_host_release_accept) host_accepts=host_accepts+1;
    if(ref_protocol_fault) faults=faults+1;
    @(negedge clk); #1;
end
endtask
task clear_events;
begin
    config_valid=0; admitted_sof=0; publish=0; retired_error=0;
    release_valid=0; host_release_valid=0; input_ready=0; host_ready=0;
    engine_idle=1;
end
endtask
task reset_all;
begin
    clear_events; rst=1; tick; tick; rst=0; tick;
end
endtask
task arm;
begin
    config_generation=41; config_valid=1; tick;
    if(VALID_CFG && !ref_config_accept) $fatal(1,"arm did not accept");
    if(!VALID_CFG && !ref_config_reject) $fatal(1,"invalid parameters armed");
    clear_events; tick;
end
endtask
task start_bank(input integer bank_id);
begin
    capture_bank=bank_id; admitted_sof=1; tick;
    clear_events;
end
endtask
task publish_good;
begin
    publish_seq=reference.next_sequence; publish=1; tick;
    clear_events; tick;
end
endtask
task claims;
begin
    input_ready=1; host_ready=1; tick; clear_events; tick;
end
endtask
task release_id(input integer bank_id);
begin
    release_bank=bank_id; host_release_bank=bank_id;
    release_camera=4; host_release_camera=4;
    release_generation=reference.generation;
    host_release_generation=reference.generation;
    release_seq=reference.\sequence [bank_id];
    host_release_seq=reference.\sequence [bank_id];
    release_token={release_generation,release_seq};
    host_release_token={host_release_generation,host_release_seq};
end
endtask
task boundary(input [31:0] seq_value, input [31:0] count_value);
begin
    // One-time idle state deposit on BOTH actual RTL instances, no force.
    // Count represents a compressed prior lifetime of completed publications.
    if(reference.state[0]!=0 || reference.state[1]!=0 || publish || rst ||
       reference.epoch_start || reference.input_valid || reference.host_valid)
        $fatal(1,"boundary setup requires quiescent legal state");
    if(seq_value==0) begin reference.armed=0; dut.armed=0; end
    reference.next_sequence=seq_value; dut.next_sequence=seq_value;
    reference.next_nonzero=(seq_value!=0); reference.next_last=(seq_value==32'hffffffff);
    dut.next_nonzero=(seq_value!=0); dut.next_last=(seq_value==32'hffffffff);
    reference.published_count=count_value; dut.published_count=count_value;
    dut.published_prefix[1]=(&count_value[3:0]);
    dut.published_prefix[2]=(&count_value[7:0]);
    dut.published_prefix[3]=(&count_value[11:0]);
    dut.published_prefix[4]=(&count_value[15:0]);
    dut.published_prefix[5]=(&count_value[19:0]);
    dut.published_prefix[6]=(&count_value[23:0]);
    dut.published_prefix[7]=(&count_value[27:0]);
    compare_outputs;
end
endtask
initial begin
    #1; @(negedge clk); reset_all; arm;
    if(VALID_CFG) begin
        start_bank(0); publish_good;
        repeat(7) tick; // descriptor backpressure
        release_id(0); release_valid=1; host_release_valid=1; tick;
        if(!ref_release_reject || !ref_host_release_reject)
            $fatal(1,"unclaimed lease released");
        clear_events;
        input_ready=1; host_ready=1; release_valid=1; host_release_valid=1; tick;
        if(!ref_release_reject || !ref_host_release_reject)
            $fatal(1,"same-edge claim/release authorized");
        clear_events;
        start_bank(1); publish_good; claims;
        if(ref_bank0_state!=2 || ref_bank1_state!=2) $fatal(1,"dual HELD missing");
        release_id(0); release_valid=1; tick; clear_events;
        if(HOST_REQUIRED && ref_bank0_state!=2) $fatal(1,"freed before host");
        host_release_valid=1; tick; clear_events; tick;
        if(ref_bank0_state!=0) $fatal(1,"completed lease not freed");
        release_id(1); host_release_valid=1; tick; clear_events;
        if(ref_bank1_state!=2) $fatal(1,"freed before cooperative release");
        release_valid=1; tick; clear_events; tick;
        if(ref_bank1_state!=0) $fatal(1,"second lease not freed");
        release_valid=1; host_release_valid=1; tick;
        if(!ref_release_reject || !ref_host_release_reject) $fatal(1,"duplicate release accepted");
        clear_events;

        // Every combination of seven event/handshake bits against an actual
        // HELD bank0 plus WRITING bank1. Identity errors vary independently.
        for(mask=0;mask<128;mask=mask+1) begin
            reset_all; arm; start_bank(0); publish_good; claims; start_bank(1);
            release_id(0);
            config_valid=mask[0]; config_generation=42;
            admitted_sof=mask[1]; capture_bank=0;
            publish=mask[2]; publish_seq=reference.next_sequence;
            retired_error=mask[3]; release_valid=mask[4];
            host_release_valid=mask[5]; input_ready=mask[6]; host_ready=mask[6];
            tick; clear_events; tick;
        end
        // SOF and publication on the same bank use old WRITING state.
        reset_all; arm; admitted_sof=1; publish=1; publish_seq=1; tick;
        if(!ref_protocol_fault || ref_published_count!=0) $fatal(1,"SOF/publish priority");
        // ARM accepts, but illegally asserted admitted_sof faults/disarms.
        reset_all; config_valid=1; config_generation=51; admitted_sof=1; tick;
        if(!ref_config_accept || !ref_protocol_fault || ref_armed) $fatal(1,"ARM/SOF priority");
        // Publication wins over retired_error, even when sequence is invalid.
        reset_all; arm; start_bank(0); publish=1; publish_seq=0; retired_error=1; tick;
        if(!ref_protocol_fault || ref_failed_count!=0 || ref_bank0_state!=1)
            $fatal(1,"invalid publish/error priority");
        reset_all; arm; start_bank(0); publish=1; publish_seq=1; retired_error=1; tick;
        if(ref_protocol_fault || ref_failed_count!=0 || ref_bank0_state!=2)
            $fatal(1,"valid publish/error priority");
        // Every nibble carry boundary, full counter wrap, sequence wrap.
        for(n=1;n<=8;n=n+1) begin
            reset_all; arm; boundary(32'hfffffffe,(64'h1<<(n*4))-1);
            start_bank(0); publish_good; claims;
            $display("PREFIX_CARRY width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);
            if(ref_published_count !== ((64'h1<<(n*4)) & 32'hffffffff))
                $fatal(1,"publication count carry boundary");
            release_id(0); release_valid=1; host_release_valid=1; tick; clear_events; tick;
            start_bank(1); publish_good;
            if(ref_armed || reference.next_sequence!=0 || !ref_lease_block)
                $fatal(1,"sequence wrap authorized another frame");
            claims; release_id(1); release_valid=1; host_release_valid=1; tick; clear_events; tick;
            config_generation=42; config_valid=1; tick;
            if(!ref_config_accept || reference.next_sequence!=1) $fatal(1,"wrap rearm failed");
            clear_events; tick;
            release_id(0); release_generation=41; host_release_generation=41;
            release_valid=1; host_release_valid=1; tick;
            if(!ref_release_reject || !ref_host_release_reject) $fatal(1,"stale release accepted");
        end
        reset_all; arm; boundary(0,0); start_bank(0);
        publish_seq=0; publish=1; tick;
        if(!ref_protocol_fault || ref_published_count!=0) $fatal(1,"zero sequence accepted");

        // Enter all-ones from all-ones-minus-one, hold, and leave across carry.
        // Every prefix width is checked on both sides of the publication edge.
        for(n=1;n<=8;n=n+1) begin
            reset_all; arm; boundary(1,(64'h1<<(n*4))-2);
            start_bank(0); publish_good;
            if(ref_published_count!==(((64'h1<<(n*4))-1)&32'hffffffff))
                $fatal(1,"prefix enter-all-ones count");
            $display("PREFIX_ENTER_ONES width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);
            repeat(3) tick; claims; release_id(0);
            release_valid=1; host_release_valid=HOST_REQUIRED; tick;
            clear_events; tick; start_bank(1); publish_good;
            if(ref_published_count!==((64'h1<<(n*4))&32'hffffffff))
                $fatal(1,"prefix leave-all-ones count");
            $display("PREFIX_LEAVE_ONES width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);
        end
        // Reset wins over valid publication, config and error, at full carry.
        reset_all; arm; boundary(1,32'hffffffff); start_bank(0);
        rst=1; publish=1; publish_seq=1; config_valid=1;
        config_generation=52; retired_error=1; tick;
        if(ref_published_count!=0 || ref_config_accept || ref_failed_count!=0)
            $fatal(1,"reset/config/publish/error priority");
        $display("PREFIX_RESET_PRIORITY_PASS");
        rst=0; clear_events; tick;
        // Legal idle reconfiguration plus invalid publication: no count change.
        reset_all; arm; boundary(1,32'hfffffffe);
        config_valid=1; config_generation=52; publish=1; publish_seq=1;
        retired_error=1; tick;
        if(!ref_config_accept || !ref_protocol_fault || ref_published_count!=32'hfffffffe)
            $fatal(1,"config/publish/error priority");
        $display("PREFIX_CONFIG_PUBLISH_PRIORITY_PASS");
        // Abort/rollback retains count and predicates, following SOF is legal.
        reset_all; arm; boundary(1,32'hfffffffe); start_bank(0);
        retired_error=1; tick; clear_events; tick;
        if(ref_bank0_state!=0 || ref_published_count!=32'hfffffffe || ref_failed_count!=1)
            $fatal(1,"abort changed count");
        start_bank(0); publish_good; claims;
        release_id(0); release_valid=1; host_release_valid=HOST_REQUIRED; tick;
        clear_events; tick;
        if(ref_bank0_state!=0) $fatal(1,"dual consumer copy ack did not release");
        start_bank(1); publish_good;
        if(ref_published_count!=0) $fatal(1,"full rollover failed");
        $display("PREFIX_ABORT_COPY_ACK_ROLLOVER_PASS count=%h prefix=%b",ref_published_count,dut.published_prefix);

        // Sustained fault-free randomized operation reaches leases, releases,
        // retirement and reconfiguration instead of sitting in latched fault.
        reset_all; arm;
        for(n=0;n<20000;n=n+1) begin
            clear_events; r=$random(seed);
            capture_bank=r[8];
            config_valid=ref_config_ready && (r[7:0]==0);
            config_generation=42+n;
            #1;
            admitted_sof=!ref_lease_block && r[9];
            publish=reference.state[reference.writing_bank]==1 && r[20];
            publish_seq=reference.next_sequence;
            retired_error=r[30] && r[31];
            input_ready=r[12]; host_ready=r[13];
            release_id(r[14]); release_valid=r[15]; host_release_valid=r[16];
            if(r[24:21]==0) release_token=release_token^1;
            if(r[28:25]==0) host_release_camera=5;
            tick;
            if(ref_protocol_fault) $fatal(1,"legal random traffic faulted");
        end
    end
    // Deterministic driven sequences include protocol-valid and adversarial
    // events, repeated reset/rearm, wrong identity fields, and busy engine.
    reset_all;
    for(n=0;n<30000;n=n+1) begin
        clear_events;
        r=$random(seed);
        if(n%251==0) begin reset_all; arm; end
        engine_idle=r[0] || r[1];
        config_valid=(r[7:2]==0); config_generation=41+(n%23);
        capture_bank=r[8];
        admitted_sof=(!ref_lease_block && r[9]) || (r[19:10]==0);
        publish=(reference.state[reference.writing_bank]==1 && r[20]) || r[29:21]==0;
        publish_seq=reference.next_sequence;
        if(r[25:21]==1) publish_seq=publish_seq ^ (32'h1<<r[14:10]);
        retired_error=r[30] && r[31];
        input_ready=r[12]; host_ready=r[13];
        release_id(r[14]); release_valid=r[15]; host_release_valid=r[16];
        case(r[19:17])
            1: release_camera=5;
            2: host_release_camera=5;
            3: release_token=release_token^64'h100000000;
            4: host_release_token=host_release_token^1;
            5: release_seq=release_seq+1;
            6: host_release_generation=host_release_generation+1;
        endcase
        tick;
    end
    $display("LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS cycles=%0d public_outputs=36 publications=%0d retirements=%0d coop_accepts=%0d host_accepts=%0d fault_cycles=%0d",cycles,pubs,errors,coop_accepts,host_accepts,faults);
    $finish;
end
initial begin #10000000; $fatal(1,"timeout"); end

endmodule
