`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_tx_request_arbiter.sv
 * @brief Verify ownership, bundle stability, round-robin choice, and ACK routing.
 *
 * @details
 * The test drives controlled TX acknowledgements without a PCIe link model.
 * It proves only the project-owned request arbitration contract. Native input
 * is assumed to assert at most one request type and to hold its complete bundle
 * through the selected ACK edge.
 */
module tb_rgb565_pg2l50h_pcie_tx_request_arbiter;
    logic clk = 1'b0;
    logic rst_n = 1'b0;

    logic native_user_data = 1'b0;
    logic native_mwr32_req = 1'b0;
    logic native_mwr32_ack;
    logic native_mwr64_req = 1'b0;
    logic native_mwr64_ack;
    logic native_mrd32_req = 1'b0;
    logic native_mrd32_ack;
    logic native_mrd64_req = 1'b0;
    logic native_mrd64_ack;
    logic [9:0] native_length = 10'd0;
    logic [63:0] native_addr = 64'd0;
    logic [31:0] native_data = 32'd0;

    logic camera_mwr32_req = 1'b0;
    logic camera_mwr32_ack;
    logic [9:0] camera_length = 10'd1;
    logic [63:0] camera_addr = 64'd0;
    logic [31:0] camera_data = 32'd0;

    logic tx_user_data;
    logic tx_mwr32_req;
    logic tx_mwr32_ack = 1'b0;
    logic tx_mwr64_req;
    logic tx_mwr64_ack = 1'b0;
    logic tx_mrd32_req;
    logic tx_mrd32_ack = 1'b0;
    logic tx_mrd64_req;
    logic tx_mrd64_ack = 1'b0;
    logic [9:0] tx_length;
    logic [63:0] tx_addr;
    logic [31:0] tx_data;

    rgb565_pg2l50h_pcie_tx_request_arbiter u_dut (
        .rst_n(rst_n),
        .clk(clk),
        .native_user_define_data_flag(native_user_data),
        .native_mwr32_req(native_mwr32_req),
        .native_mwr32_req_ack(native_mwr32_ack),
        .native_mwr64_req(native_mwr64_req),
        .native_mwr64_req_ack(native_mwr64_ack),
        .native_mrd32_req(native_mrd32_req),
        .native_mrd32_req_ack(native_mrd32_ack),
        .native_mrd64_req(native_mrd64_req),
        .native_mrd64_req_ack(native_mrd64_ack),
        .native_req_length(native_length),
        .native_req_addr(native_addr),
        .native_req_data(native_data),
        .camera_mwr32_req(camera_mwr32_req),
        .camera_mwr32_req_ack(camera_mwr32_ack),
        .camera_req_length(camera_length),
        .camera_req_addr(camera_addr),
        .camera_req_data(camera_data),
        .tx_user_define_data_flag(tx_user_data),
        .tx_mwr32_req(tx_mwr32_req),
        .tx_mwr32_req_ack(tx_mwr32_ack),
        .tx_mwr64_req(tx_mwr64_req),
        .tx_mwr64_req_ack(tx_mwr64_ack),
        .tx_mrd32_req(tx_mrd32_req),
        .tx_mrd32_req_ack(tx_mrd32_ack),
        .tx_mrd64_req(tx_mrd64_req),
        .tx_mrd64_req_ack(tx_mrd64_ack),
        .tx_req_length(tx_length),
        .tx_req_addr(tx_addr),
        .tx_req_data(tx_data)
    );

    always #5ns clk = ~clk;

    task automatic clear_requests;
        begin
            native_mwr32_req = 1'b0;
            native_mwr64_req = 1'b0;
            native_mrd32_req = 1'b0;
            native_mrd64_req = 1'b0;
            camera_mwr32_req = 1'b0;
            tx_mwr32_ack = 1'b0;
            tx_mwr64_ack = 1'b0;
            tx_mrd32_ack = 1'b0;
            tx_mrd64_ack = 1'b0;
        end
    endtask

    task automatic apply_reset;
        begin
            @(negedge clk);
            rst_n = 1'b0;
            clear_requests();
            repeat (2) @(negedge clk);
            rst_n = 1'b1;
            @(posedge clk);
            #1ns;
            if (tx_mwr32_req || tx_mwr64_req || tx_mrd32_req || tx_mrd64_req ||
                native_mwr32_ack || native_mwr64_ack || native_mrd32_ack ||
                native_mrd64_ack || camera_mwr32_ack)
                $fatal(1, "Arbiter was not idle after reset");
        end
    endtask

    initial begin
        #10us;
        $fatal(1, "PCIe TX request arbiter timeout");
    end

    initial begin
        apply_reset();

        // Native MWR64 passes through and updates the retained MWR data mode.
        @(negedge clk);
        native_user_data = 1'b1;
        native_length = 10'd4;
        native_addr = 64'h0000_0001_0000_0000;
        native_data = 32'h89ab_cdef;
        native_mwr64_req = 1'b1;
        @(posedge clk);
        #1ns;
        if (!tx_mwr64_req || tx_mwr32_req || tx_mrd32_req || tx_mrd64_req ||
            tx_length !== 10'd4 || tx_addr !== 64'h0000_0001_0000_0000)
            $fatal(1, "Native MWR64 bundle was not selected");
        @(negedge clk);
        tx_mwr64_ack = 1'b1;
        #1ns;
        if (!native_mwr64_ack || native_mwr32_ack || native_mrd32_ack ||
            native_mrd64_ack || camera_mwr32_ack)
            $fatal(1, "Native MWR64 ACK routing mismatch");
        @(posedge clk);
        #1ns;
        if (!tx_user_data)
            $fatal(1, "Native MWR64 mode was not retained");
        @(negedge clk);
        native_mwr64_req = 1'b0;
        tx_mwr64_ack = 1'b0;

        // Native MRD32 uses the same bundle but must not replace MWR data mode.
        @(negedge clk);
        native_user_data = 1'b0;
        native_length = 10'd7;
        native_addr = 64'h0000_0000_7000_0000;
        native_data = 32'h7654_3210;
        native_mrd32_req = 1'b1;
        @(posedge clk);
        #1ns;
        if (!tx_mrd32_req || tx_mwr32_req || tx_mwr64_req || tx_mrd64_req ||
            tx_length !== 10'd7 || tx_addr !== 64'h0000_0000_7000_0000)
            $fatal(1, "Native MRD32 bundle was not selected");
        @(negedge clk);
        tx_mrd32_ack = 1'b1;
        #1ns;
        if (!native_mrd32_ack || native_mwr32_ack || native_mwr64_ack ||
            native_mrd64_ack || camera_mwr32_ack)
            $fatal(1, "Native MRD32 ACK routing mismatch");
        @(posedge clk);
        #1ns;
        if (!tx_user_data)
            $fatal(1, "Native MRD32 incorrectly changed retained MWR mode");
        @(negedge clk);
        native_mrd32_req = 1'b0;
        tx_mrd32_ack = 1'b0;

        apply_reset();

        // Native request owns the entire four-request bundle until its ACK.
        @(negedge clk);
        native_user_data = 1'b0;
        native_length = 10'd9;
        native_addr = 64'h0000_0001_2345_6000;
        native_data = 32'h1122_3344;
        native_mrd64_req = 1'b1;
        @(posedge clk);
        #1ns;
        if (!tx_mrd64_req || tx_user_data || tx_length !== 10'd9 ||
            tx_addr !== 64'h0000_0001_2345_6000 || tx_data !== 32'h1122_3344)
            $fatal(1, "Native bundle was not selected");

        @(negedge clk);
        camera_mwr32_req = 1'b1;
        camera_addr = 64'h8000;
        camera_data = 32'hdead_beef;
        #1ns;
        if (!tx_mrd64_req || tx_mwr32_req || tx_addr !== 64'h0000_0001_2345_6000)
            $fatal(1, "Competing camera request changed native ownership");
        tx_mrd64_ack = 1'b1;
        #1ns;
        if (!native_mrd64_ack || camera_mwr32_ack)
            $fatal(1, "Native ACK was not isolated to the native owner");
        @(posedge clk);
        @(negedge clk);
        native_mrd64_req = 1'b0;
        camera_mwr32_req = 1'b0;
        tx_mrd64_ack = 1'b0;

        // After a native completion, simultaneous requests choose camera.
        @(negedge clk);
        native_user_data = 1'b0;
        native_length = 10'd3;
        native_addr = 64'h1000;
        native_data = 32'haaaa_5555;
        native_mwr32_req = 1'b1;
        camera_length = 10'd1;
        camera_addr = 64'h4000;
        camera_data = 32'h5566_7788;
        camera_mwr32_req = 1'b1;
        @(posedge clk);
        #1ns;
        if (!tx_mwr32_req || tx_user_data || tx_length !== 10'd1 ||
            tx_addr !== 64'h4000 || tx_data !== 32'h5566_7788)
            $fatal(1, "Round-robin did not choose camera after native completion");

        @(negedge clk);
        native_addr = 64'hffff_ffff_ffff_fffc;
        native_data = 32'hcafe_f00d;
        #1ns;
        if (tx_addr !== 64'h4000 || tx_data !== 32'h5566_7788)
            $fatal(1, "Unselected native changes corrupted camera bundle");
        tx_mwr32_ack = 1'b1;
        #1ns;
        if (!camera_mwr32_ack || native_mwr32_ack)
            $fatal(1, "Camera ACK was not isolated to the camera owner");
        @(posedge clk);
        #1ns;
        if (!tx_user_data)
            $fatal(1, "Camera user-defined-data mode was not retained after ACK");
        @(negedge clk);
        clear_requests();

        // Camera completion makes native first on the next simultaneous race.
        @(negedge clk);
        native_user_data = 1'b0;
        native_length = 10'd1;
        native_addr = 64'h2000;
        native_data = 32'h0102_0304;
        camera_addr = 64'h5000;
        camera_data = 32'h0506_0708;
        native_mwr32_req = 1'b1;
        camera_mwr32_req = 1'b1;
        @(posedge clk);
        #1ns;
        if (!tx_mwr32_req || !tx_user_data || tx_addr !== 64'h2000 ||
            tx_data !== 32'h0102_0304)
            $fatal(1, "Round-robin did not return priority to native");

        @(negedge clk);
        tx_mwr32_ack = 1'b1;
        #1ns;
        if (!native_mwr32_ack || camera_mwr32_ack)
            $fatal(1, "Native MWR ACK routing mismatch");
        @(posedge clk);
        #1ns;
        if (tx_user_data)
            $fatal(1, "Native RAM-data mode was not retained after ACK");

        // Reset must cancel ownership and suppress stale ACK routing.
        @(negedge clk);
        rst_n = 1'b0;
        tx_mwr32_ack = 1'b1;
        #1ns;
        if (tx_mwr32_req || native_mwr32_ack || camera_mwr32_ack)
            $fatal(1, "Reset did not clear request ownership");
        repeat (2) @(negedge clk);
        clear_requests();
        rst_n = 1'b1;
        repeat (2) @(posedge clk);

        $display("INFO: native/camera PCIe TX request arbitration verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
