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
    // Accelerated boundary setup only: preserve every redundant invariant.
    reference.next_sequence=seq_value; dut.next_sequence=seq_value;
    dut.next_nonzero=(seq_value!=0); dut.next_last=(seq_value==32'hffffffff);
    reference.published_count=count_value; dut.published_count=count_value;
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
    $display("LEASE_TC04_DIFF_PASS cycles=%0d public_outputs=OUTPUT_COUNT publications=%0d retirements=%0d coop_accepts=%0d host_accepts=%0d fault_cycles=%0d",cycles,pubs,errors,coop_accepts,host_accepts,faults);
    $finish;
end
initial begin #10000000; $fatal(1,"timeout"); end
