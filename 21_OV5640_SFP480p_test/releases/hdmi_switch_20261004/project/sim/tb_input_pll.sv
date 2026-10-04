`timescale 1ns/1ps
module tb_input_pll;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg clk=0, reset_n=0;
    reg [7:0] data=0;
    integer source_pixels=0;
    real half_period=3.367;
    always #(half_period) clk=~clk;
    wire [18:0] video;
    hdmi_720p_capture dut(.pclk(clk),.out_clk(clk),.request_n(reset_n),
        .capture_ready(1'b1),.vs_in(1'b0),.hs_in(1'b0),.de_in(1'b0),
        .r_in(data),.g_in(data),.b_in(data),.video(video),.fault(),.format_ok());
    realtime source_edge=0, feedback_edge=0, sample_edge=0;
    real period, phase, feedback_phase;
    integer checks=0;
    always @(posedge clk) begin
        source_edge=$realtime;
        source_pixels=source_pixels+1;
        // Exercise both ends of the unchanged external arrival interval.
        data <= #(source_pixels%2 ? 4.0 : 0.0) source_pixels;
    end
    always @(posedge dut.feedback_clk) feedback_edge=$realtime;
    always @(posedge dut.sample_clk) begin
        if(dut.input_locked && reset_n && sample_edge>0) begin
            period=$realtime-sample_edge;
            phase=$realtime-source_edge;
            feedback_phase=$realtime-feedback_edge;
            if(checks<5) $display("PLL edge: period=%0.3f input_phase=%0.3f feedback_phase=%0.3f",period,phase,feedback_phase);
            if(period<2*half_period-0.05 || period>2*half_period+0.05)
                $fatal(1,"PLL period mismatch %0.3f",period);
            if(feedback_phase<2*half_period*43.0/64.0-0.06 ||
               feedback_phase>2*half_period*43.0/64.0+0.06)
                $fatal(1,"PLL phase mismatch %0.3f",feedback_phase);
            if(phase<2*half_period*43.0/64.0-0.10 ||
               phase>2*half_period*43.0/64.0+0.10)
                $fatal(1,"PLL input phase mismatch %0.3f",phase);
            checks=checks+1;
        end
        sample_edge=$realtime;
        #0.001;
        if(dut.input_locked && reset_n && dut.r!==data)
            $fatal(1,"0/4ns arrival captured incorrect data");
    end
    initial begin
        #100 reset_n=1;
        #10000;
        if(checks<317) $fatal(1,"PLL did not acquire: checks=%0d",checks);
        $display("PLL 148.5MHz PASS checks=%0d",checks);
        // Explicit status-loss injection tests the common-flush indication
        // independently of the vendor analog model's lock-loss threshold.
        force dut.input_locked=1'b0;
        #100;
        if(!dut.fault || dut.wr_rst_n || dut.rd_rst_n)
            $fatal(1,"acquired PLL loss did not fault/reset both FIFO domains");
        release dut.input_locked;
        reset_n=0; #100;
        if(dut.wr_rst_n || dut.rd_rst_n) $fatal(1,"lock/reset did not assert resets");
        checks=0; sample_edge=0; half_period=6.734; reset_n=1;
        #20000;
        if(checks<317) $fatal(1,"PLL 74.25MHz did not acquire: checks=%0d",checks);
        $display("TEST PASS: unmodified vendor PLL/global feedback 43/64 phase, 148.5/74.25MHz, 0/4ns arrivals, lock reset; checks=%0d",checks);
        $finish;
    end
endmodule
