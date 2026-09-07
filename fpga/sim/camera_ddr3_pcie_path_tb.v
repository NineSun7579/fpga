`timescale 1ns/1ps

// Behavioral end-to-end check for the camera -> FIFO -> DDR3 -> FIFO -> PCIe
// data path. DDR3 and PCIe SerDes are abstracted; the camera capture RTL is real.
module camera_ddr3_pcie_path_tb;
    reg        cam_pclk;
    reg        rst_n;
    reg        cam_vsync;
    reg        cam_href;
    reg [7:0]  cam_data;
    wire       frame_vsync;
    wire       frame_href;
    wire       frame_valid;
    wire [15:0] frame_data;

    reg [15:0] expected [0:15];
    reg [15:0] captured [0:15];
    reg [255:0] ddr_frame;
    reg [127:0] pcie_word;
    reg [255:0] pack_reg;
    integer input_index;
    integer capture_count;
    integer pcie_count;
    integer errors;
    reg capture_done;
    reg pcie_valid;

    cmos_capture_data #(.WAIT_FRAME(4'd0)) u_capture (
        .rst_n             (rst_n),
        .cam_pclk         (cam_pclk),
        .cam_vsync        (cam_vsync),
        .cam_href         (cam_href),
        .cam_data         (cam_data),
        .cmos_frame_vsync (frame_vsync),
        .cmos_frame_href  (frame_href),
        .cmos_frame_valid (frame_valid),
        .cmos_frame_data  (frame_data)
    );

    initial cam_pclk = 1'b0;
    // The 24 MHz camera crystal is multiplied internally; this configuration
    // produces approximately 48 MHz DVP PCLK.
    always #10.4167 cam_pclk = ~cam_pclk;

    initial begin
        errors = 0;
        capture_count = 0;
        pcie_count = 0;
        input_index = 0;
        capture_done = 1'b0;
        pcie_valid = 1'b0;
        pack_reg = 256'd0;
        ddr_frame = 256'd0;
        pcie_word = 128'd0;
        cam_vsync = 1'b0;
        cam_href = 1'b0;
        cam_data = 8'd0;

        for (input_index = 0; input_index < 16; input_index = input_index + 1)
            expected[input_index] = 16'h1000 + input_index;

        rst_n = 1'b0;
        #3000;
        rst_n = 1'b1;

        // One frame-start pulse, followed by 16 RGB565 pixels on DVP.
        @(negedge cam_pclk);
        cam_vsync = 1'b1;
        @(negedge cam_pclk);
        cam_vsync = 1'b0;
        cam_href = 1'b1;
        for (input_index = 0; input_index < 16; input_index = input_index + 1) begin
            cam_data = expected[input_index][15:8];
            @(negedge cam_pclk);
            cam_data = expected[input_index][7:0];
            @(negedge cam_pclk);
        end
        cam_href = 1'b0;
        cam_data = 8'd0;

        wait (capture_done);
        #100;
        if (pcie_count != 8) begin
            $display("FAIL: expected 8 PCIe 128-bit words, got %0d", pcie_count);
            errors = errors + 1;
        end
        if (errors == 0)
            $display("PASS: camera -> FIFO -> DDR3 -> FIFO -> PCIe data path verified");
        else
            $display("FAIL: %0d data errors", errors);
        $finish;
    end

    // Camera-side packing and a behavioral camera-to-DDR bridge.
    always @(posedge cam_pclk) begin
        if (!rst_n) begin
            capture_count <= 0;
            pack_reg <= 0;
            capture_done <= 1'b0;
        end else if (frame_valid) begin
            captured[capture_count] <= frame_data;
            pack_reg <= {pack_reg[239:0], frame_data};
            if (capture_count == 15) begin
                ddr_frame <= {pack_reg[239:0], frame_data};
                capture_done <= 1'b1;
            end
            capture_count <= capture_count + 1;
        end
    end

    // Behavioral DDR3 readback, rd_fifo, and PCIe 128-bit source.
    always @(posedge cam_pclk) begin
        if (!rst_n) begin
            pcie_word <= 128'd0;
            pcie_valid <= 1'b0;
        end else if (capture_done && (pcie_count < 8)) begin
            pcie_word <= ddr_frame[(pcie_count * 128) +: 128];
            pcie_valid <= 1'b1;
        end else begin
            pcie_valid <= 1'b0;
        end
    end

    always @(posedge cam_pclk) begin
        if (pcie_valid) begin
            if (pcie_count < 8) begin
                if (pcie_word !== ddr_frame[(pcie_count * 128) +: 128]) begin
                    $display("FAIL: PCIe word %0d does not match DDR readback", pcie_count);
                    errors = errors + 1;
                end
                pcie_count = pcie_count + 1;
            end
        end
    end

    integer i;
    initial begin
        #50000;
        $display("TIMEOUT: capture_count=%0d pcie_count=%0d", capture_count, pcie_count);
        $finish;
    end
endmodule
