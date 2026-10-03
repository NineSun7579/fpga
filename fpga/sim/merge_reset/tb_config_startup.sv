`timescale 1ns/1ps
module tb_config_startup;
    reg sys_clk=0, cfg_clk=0;
    reg sys_run=1, cfg_run=1;
    always #10 if(sys_run) sys_clk=~sys_clk;
    always #20 if(cfg_run) cfg_clk=~cfg_clk;
    reg rstn=0;
    wire camera_rstn, c2, pwnd, initial_en;
    power_on_delay power_delay(sys_clk,rstn,camera_rstn,c2,pwnd,initial_en);
    wire done, scl, clock_i2c;
    wire [8:0] index;
    tri1 sda;
    reg_config dut(cfg_clk,camera_rstn,initial_en,done,scl,sda,clock_i2c,index);
    // Actual core releases each ACK bit at old counts 11/20/29/38;
    // cyc_count becomes 12/21/30/39, then samples SDA on the next posedge.
    wire ack_slot=(dut.u1.cyc_count==12 || dut.u1.cyc_count==21 ||
                   dut.u1.cyc_count==30 || dut.u1.cyc_count==39);
    assign sda = camera_rstn && ack_slot ? 1'b0 : 1'bz;

    wire legacy_done, legacy_scl, legacy_i2c_clk;
    wire [8:0] legacy_index;
    tri1 legacy_sda;
    reg_config_legacy legacy(cfg_clk,camera_rstn,initial_en,legacy_done,
                            legacy_scl,legacy_sda,legacy_i2c_clk,legacy_index);
    // Separate directly clocked legacy core proves reset loss with stopped clock.
    reg neg_clk=0, neg_run=1, neg_rstn=0, neg_start=0;
    always #25 if(neg_run) neg_clk=~neg_clk;
    tri1 neg_sda;
    wire neg_ack,neg_end,neg_scl;
    i2c_com_legacy negative_core(neg_clk,neg_rstn,neg_ack,32'h78123456,
                                neg_start,neg_end,neg_scl,neg_sda);
    wire nc_done,nc_scl,nc_clk;
    tri1 nc_sda;
    wire [8:0] nc_index;
    reg_config_legacy negative_config(cfg_clk,neg_rstn,1'b0,
                                      nc_done,nc_scl,nc_sda,nc_clk,nc_index);

    integer starts=0, stops=0, completed=0, ack_bits=0, bits=0;
    integer runs=0;
    reg transaction=0;
    reg [31:0] serial_word=0, expected_word=0;
    reg [31:0] first_run_words[0:356];
    reg [5:0] count_sample;
    always @(negedge sda) if(camera_rstn && scl===1 && dut.u1.cyc_count==2) begin
        if(!initial_en) $fatal(1,"transaction before initial_en");
        if(transaction) $fatal(1,"nested START");
        if(index!==9'(starts) || starts>=357) $fatal(1,"command order/count");
        expected_word={8'h78,dut.reg_data};
        if(dut.i2c_data!==expected_word || $isunknown(expected_word))
            $fatal(1,"unknown/wrong command data at index %d",index);
        transaction=1; bits=0; serial_word=0; starts=starts+1;
    end
    always @(posedge scl) if(camera_rstn && transaction) begin
        count_sample=dut.u1.cyc_count;
        if(count_sample>=4 && count_sample<=39) begin
            if(count_sample==12 || count_sample==21 || count_sample==30 || count_sample==39) begin
                if(sda!==0) $fatal(1,"ACK not low");
                ack_bits=ack_bits+1;
            end else begin
                if($isunknown(sda)) $fatal(1,"unknown serial data");
                serial_word={serial_word[30:0],sda}; bits=bits+1;
            end
        end
    end
    always @(posedge sda) if(camera_rstn && scl===1 && transaction && dut.u1.cyc_count==42) begin
        if(bits!=32 || serial_word!==expected_word) $fatal(1,"serial payload mismatch bits=%d got=%h expected=%h",bits,serial_word,expected_word);
        if(runs==0) first_run_words[stops]=serial_word;
        else if(serial_word!==first_run_words[stops]) $fatal(1,"rerun command changed");
        transaction=0; stops=stops+1;
    end
    always @(posedge dut.tr_end) if(camera_rstn) begin
        #1;
        if(transaction || stops!=completed+1) $fatal(1,"completion before STOP");
        // ACK is active-low success, OR of three sampled registers.
        if(dut.ack!==0) $fatal(1,"core did not sample successful ACK");
        completed=completed+1;
    end
    always @(posedge clock_i2c) if(camera_rstn && !initial_en) begin
        #1;
        if(dut.start!==0 || index!==0 || done!==0 || dut.config_step!==0 || scl!==1 || sda!==1)
            $fatal(1,"configuration active before enable");
    end
    task check_config_reset;
        begin
            #1;
            if(done!==0 || index!==0 || clock_i2c!==0 || dut.clock_20k_cnt!==0 ||
               dut.config_step!==0 || dut.start!==0 || dut.u1.cyc_count!==63 ||
               dut.u1.tr_end!==0 || {dut.u1.ack1,dut.u1.ack2,dut.u1.ack3}!==3'b111 ||
               dut.u1.sclk!==1 || dut.u1.reg_sdat!==1 || scl!==1 || sda!==1)
                $fatal(1,"config/core reset unknown or incomplete");
        end
    endtask
    task run_config;
        begin
            starts=0; stops=0; completed=0; ack_bits=0;
            @(negedge sys_clk); rstn=1;
            @(posedge camera_rstn); #1; check_config_reset;
            if(initial_en!==0) $fatal(1,"power timing skipped initial enable delay");
            @(posedge initial_en);
            if(starts!=0 || completed!=0) $fatal(1,"commands during power delay");
            @(posedge done); #1;
            if(index!==357 || starts!=357 || stops!=357 || completed!=357 || ack_bits!=1428)
                $fatal(1,"wrong totals index=%d start=%d stop=%d complete=%d ACK=%d",index,starts,stops,completed,ack_bits);
            runs=runs+1;
            $display("CONFIG PASS run=%0d START=%0d STOP=%0d completed=%0d ACKbits=%0d index=%0d",runs,starts,stops,completed,ack_bits,index);
            repeat(5) @(posedge clock_i2c);
            if(starts!=357 || completed!=357) $fatal(1,"transactions after done");
        end
    endtask
    initial begin
        // Give synchronous power reset its three root-clock edges.
        repeat(4) @(posedge sys_clk); check_config_reset;
        if(!$isunknown({legacy_done,legacy_index,legacy.config_step,legacy.u1.cyc_count}))
            $fatal(1,"legacy startup unexpectedly defined");
        $display("NEGATIVE PASS: actual legacy divided-clock configuration remains X during camera reset");
        // Seed only the legacy reference to isolate its ignored-enable bug.
        force negative_config.reg_conf_done_reg=0;
        force negative_config.reg_index=0;
        force negative_config.config_step=0;
        force negative_config.start=0;
        #1;
        release negative_config.reg_conf_done_reg;
        release negative_config.reg_index;
        release negative_config.config_step;
        release negative_config.start;
        neg_rstn=1;
        repeat(2) @(negedge neg_clk);
        neg_start=1;
        repeat(10) @(negedge neg_clk);
        neg_run=0;
        @(posedge negative_config.start);
        $display("NEGATIVE PASS: seeded legacy config launches START with initial_en tied low");
        // Seed completed state to isolate stale done on a stopped-clock rerun.
        force negative_config.reg_conf_done_reg=1;
        force negative_config.reg_index=357;
        force negative_config.config_step=0;
        force negative_config.start=0;
        #1;
        release negative_config.reg_conf_done_reg;
        release negative_config.reg_index;
        release negative_config.config_step;
        release negative_config.start;
        cfg_run=0;
        #1; neg_rstn=0; #1;
        if(negative_core.cyc_count===63 || negative_core.sclk===1)
            $fatal(1,"legacy core negative control not active");
        if(nc_done!==1 || nc_index!==357) $fatal(1,"legacy done did not remain stale");
        $display("NEGATIVE PASS: stopped-clock legacy core retains cyc_count=%0d; seeded completed legacy config retains done=1/index=357",negative_core.cyc_count);
        cfg_run=1;
        run_config;
        // Stop config root clock, then reset through the actual power sequencer.
        @(negedge cfg_clk); cfg_run=0;
        @(negedge sys_clk); rstn=0;
        @(negedge camera_rstn); check_config_reset;
        if(legacy_done===0 && legacy_index===0) $fatal(1,"legacy unexpectedly reset");
        #1000; check_config_reset;
        cfg_run=1;
        run_config;
        $display("TEST PASS full power startup/config rerun: 357 identical real I2C commands twice, no pre-enable START, stopped-clock async reset, negative controls");
        $finish;
    end
    initial begin #(64'd4000000000); $fatal(1,"timeout"); end
endmodule
