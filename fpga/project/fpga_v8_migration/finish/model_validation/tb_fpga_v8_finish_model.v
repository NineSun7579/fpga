// Model-specific file traffic only. ASCII, Verilog-2001.
module tb_fpga_v8_finish_model;
    reg clk;
    reg rst;
    reg [63:0] s_data;
    reg s_valid;
    wire s_ready;
    reg s_last;
    reg [15:0] scale_q16;
    reg [63:0] folded_bias_q16;
    reg [7:0] preactivation_zero_point;
    reg bypass;
    reg cfg_valid;
    wire cfg_ready;
    reg [7:0] cfg_addr;
    reg [7:0] cfg_data;
    wire [15:0] m_data;
    wire m_valid;
    reg m_ready;
    wire m_last;
    fpga_v8_conv_finish #(.LANES(2)) dut (
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
    integer cycle_number;
    integer task_id;
    integer vector_id;
    integer loaded;
    integer errors;
    reg held;
    reg [15:0] held_data;
    reg held_last;
    reg held_source;
    reg [63:0] held_source_data;
    reg held_source_last;
    initial begin
        clk = 1'b0;
        forever #5 clk = !clk;
    end
    always @(posedge clk) begin
        if (loaded) begin
            if ((s_ready !== 1'b0 && s_ready !== 1'b1) ||
                (cfg_ready !== 1'b0 && cfg_ready !== 1'b1) ||
                (m_valid !== 1'b0 && m_valid !== 1'b1)) begin
                $display("FAIL unknown handshake cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if (m_valid && ((^m_data) === 1'bx ||
                (m_last !== 1'b0 && m_last !== 1'b1))) begin
                $display("FAIL unknown output cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if (cfg_valid && (cfg_ready !== 1'b1 || s_ready !== 1'b0 ||
                dut.product_valid || dut.sum_valid || dut.byte_valid || m_valid)) begin
                $display("FAIL programming not idle cycle=%0d task=%0d", cycle_number, task_id);
                errors = errors + 1;
            end
            if (held && !rst && (m_valid !== 1'b1 || m_data !== held_data || m_last !== held_last)) begin
                $display("FAIL output stall cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            if (held_source && !rst && (s_valid !== 1'b1 || s_data !== held_source_data ||
                s_last !== held_source_last)) begin
                $display("FAIL source hold cycle=%0d", cycle_number);
                errors = errors + 1;
            end
            held = !rst && m_valid && !m_ready;
            held_data = m_data;
            held_last = m_last;
            held_source = !rst && s_valid && !s_ready;
            held_source_data = s_data;
            held_source_last = s_last;
            // Emit unknowns verbatim: Python rejects them; no X or length skip.
            $fdisplay(trace_file, "%0d %0d %0d %b %b %b %b %h %b %b %b",
                cycle_number, task_id, vector_id, s_ready, cfg_ready, m_valid, m_last,
                m_data, dut.product_valid, dut.sum_valid, dut.byte_valid);
            cycle_number = cycle_number + 1;
        end
    end
    initial begin
        rst = 1'b1;
        s_data = 64'd0;
        s_valid = 1'b0;
        s_last = 1'b0;
        scale_q16 = 16'd0;
        folded_bias_q16 = 64'd0;
        preactivation_zero_point = 8'd0;
        bypass = 1'b0;
        cfg_valid = 1'b0;
        cfg_addr = 8'd0;
        cfg_data = 8'd0;
        m_ready = 1'b0;
        loaded = 0;
        cycle_number = 0;
        errors = 0;
        held = 1'b0;
        held_source = 1'b0;
        if (!$value$plusargs("STIMULUS=%s", stimulus_path) ||
            !$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing arguments");
            $finish;
        end
        input_file = $fopen(stimulus_path, "r");
        trace_file = $fopen(trace_path, "w");
        if (!input_file || !trace_file) begin
            $display("FAIL file open");
            $finish;
        end
        begin : vectors
            forever begin
                @(negedge clk);
                fields = $fscanf(input_file, "%d %d %h %h %d %h %d %h %h %h %d %d %d %d\n",
                    rst, cfg_valid, cfg_addr, cfg_data, s_valid, s_data, s_last,
                    scale_q16, folded_bias_q16, preactivation_zero_point, bypass,
                    m_ready, task_id, vector_id);
                if (fields != 14) begin
                    if (!$feof(input_file)) begin
                        $display("FAIL malformed row fields=%0d", fields);
                        errors = errors + 1;
                    end
                    disable vectors;
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
            $display("PASS_FINISH_MODEL_TB cycles=%0d lanes=2", cycle_number);
        else
            $display("FAIL_FINISH_MODEL_TB errors=%0d", errors);
        $finish;
    end
endmodule
