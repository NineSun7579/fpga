// Focused finish pipeline testbench, ASCII and Verilog-2001.
module tb_fpga_v8_conv_finish;
    parameter integer LANES = 16;
    reg clk;
    reg rst;
    reg [LANES*32-1:0] s_data;
    reg s_valid;
    wire s_ready;
    reg s_last;
    reg [15:0] scale_q16;
    reg [LANES*32-1:0] folded_bias_q16;
    reg [7:0] preactivation_zero_point;
    reg bypass;
    reg cfg_valid;
    wire cfg_ready;
    reg [7:0] cfg_addr;
    reg [7:0] cfg_data;
    wire [LANES*8-1:0] m_data;
    wire m_valid;
    reg m_ready;
    wire m_last;

    fpga_v8_conv_finish #(.LANES(LANES)) dut (
        .clk(clk), .rst(rst), .s_data(s_data), .s_valid(s_valid),
        .s_ready(s_ready), .s_last(s_last), .scale_q16(scale_q16),
        .folded_bias_q16(folded_bias_q16),
        .preactivation_zero_point(preactivation_zero_point), .bypass(bypass),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_ready), .cfg_addr(cfg_addr),
        .cfg_data(cfg_data), .m_data(m_data), .m_valid(m_valid),
        .m_ready(m_ready), .m_last(m_last)
    );

    reg [2047:0] stimulus_path;
    reg [2047:0] trace_path;
    integer input_file;
    integer trace_file;
    integer fields;
    integer phase;
    integer cycle_number;
    integer errors;
    integer loaded;
    reg held_output;
    reg [LANES*8-1:0] held_data;
    reg held_last;
    reg held_input;
    reg [LANES*32-1:0] held_input_data;
    reg held_input_last;
    reg busy;

    initial begin
        clk = 1'b0;
        forever #5 clk = !clk;
    end

    // Observe BEFORE the accepting edge updates any pipeline register.
    always @(posedge clk) begin
        if (loaded) begin
            busy = dut.product_valid || dut.sum_valid || dut.byte_valid || m_valid;
            if (cfg_ready !== (!rst && !busy)) begin
                $display("FAIL cfg_ready cycle=%0d phase=%0d", cycle_number, phase);
                errors = errors + 1;
            end
            if (dut.lut_cfg_valid !== (cfg_valid && cfg_ready)) begin
                $display("FAIL config gating cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if ((rst || cfg_valid) && s_ready !== 1'b0) begin
                $display("FAIL source priority/reset cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if (held_output && !rst &&
                (m_valid !== 1'b1 || m_data !== held_data || m_last !== held_last)) begin
                $display("FAIL output changed under stall cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if (held_input && !rst &&
                (s_valid !== 1'b1 || s_data !== held_input_data || s_last !== held_input_last)) begin
                $display("FAIL test source violated hold cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            held_output = !rst && m_valid && !m_ready;
            held_data = m_data;
            held_last = m_last;
            held_input = !rst && s_valid && !s_ready;
            held_input_data = s_data;
            held_input_last = s_last;
            $fdisplay(trace_file, "%0d %0d %0d %0d %0d %h %0d %0d %0d %0d",
                cycle_number, s_ready, cfg_ready, m_valid, m_last, m_data,
                dut.product_valid, dut.sum_valid, dut.byte_valid, dut.lut_cfg_valid);
            cycle_number = cycle_number + 1;
        end
    end

    initial begin
        rst = 1'b1;
        s_data = {LANES*32{1'b0}};
        s_valid = 1'b0;
        s_last = 1'b0;
        scale_q16 = 16'd0;
        folded_bias_q16 = {LANES*32{1'b0}};
        preactivation_zero_point = 8'd0;
        bypass = 1'b0;
        cfg_valid = 1'b0;
        cfg_addr = 8'd0;
        cfg_data = 8'd0;
        m_ready = 1'b0;
        loaded = 0;
        cycle_number = 0;
        errors = 0;
        held_output = 1'b0;
        held_input = 1'b0;
        if (!$value$plusargs("STIMULUS=%s", stimulus_path) ||
            !$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing file arguments");
            $finish;
        end
        input_file = $fopen(stimulus_path, "r");
        trace_file = $fopen(trace_path, "w");
        if (!input_file || !trace_file) begin
            $display("FAIL cannot open files");
            $finish;
        end
        begin : read_vectors
            forever begin
                @(negedge clk);
                fields = $fscanf(input_file, "%d %d %h %h %d %h %d %h %h %h %d %d %d\n",
                    rst, cfg_valid, cfg_addr, cfg_data, s_valid, s_data, s_last,
                    scale_q16, folded_bias_q16, preactivation_zero_point,
                    bypass, m_ready, phase);
                if (fields != 13) begin
                    if (!$feof(input_file)) begin
                        $display("FAIL malformed stimulus fields=%0d", fields);
                        errors = errors + 1;
                    end
                    disable read_vectors;
                end
                loaded = 1;
                @(posedge clk);
                #1;
            end
        end
        loaded = 0;
        $fclose(input_file);
        $fclose(trace_file);
        if (errors == 0)
            $display("PASS_FINISH_TB lanes=%0d cycles=%0d", LANES, cycle_number);
        else
            $display("FAIL_FINISH_TB lanes=%0d errors=%0d", LANES, errors);
        $finish;
    end
endmodule
