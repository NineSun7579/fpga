// H2F chunk RAM reads have one clock latency. Keep partial 128-bit words
// across chunks, so a 4092-byte intermediate chunk contributes 255 full words
// and 12 carry bytes, never a padded word in the middle of a transfer.
reg [31:0] rx_cnt;
reg [31:0] rx_bytes_total, rx_chunk_bytes;
reg [127:0] rx_pack_data, rx_fifo_write_data;
reg [4:0] rx_pack_bytes;
reg rx_fifo_write_en, rx_copy_active, rx_transaction_complete;
reg fpga_rx_clk_en_d;
reg fpga_rx_done;
wire [31:0] rx_input_bytes = ((fpga_ddr3_length - rx_chunk_bytes) >= 16) ?
                            32'd16 : fpga_ddr3_length - rx_chunk_bytes;
wire [127:0] rx_input_mask = {128{1'b1}} >> ((32'd16-rx_input_bytes)*8);
wire [255:0] rx_merge_data = {128'd0,rx_pack_data} |
    ({128'd0,(fpga_rx_data & rx_input_mask)} << (rx_pack_bytes*8));
wire [5:0] rx_merge_bytes = {1'b0,rx_pack_bytes}+rx_input_bytes[5:0];
assign fpga_rx_clk_en = fpga_rx_clk_en_r;
assign fpga_rx_addr = fpga_rx_addr_r;

always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        fpga_rx_clk_en_r <= 0; fpga_rx_clk_en_d <= 0;
        fpga_rx_addr_r <= 0; rx_cnt <= 0;
        rx_bytes_total <= 0; rx_chunk_bytes <= 0;
        rx_pack_data <= 0; rx_pack_bytes <= 0;
        rx_fifo_write_en <= 0; rx_fifo_write_data <= 0;
        rx_copy_active <= 0; rx_transaction_complete <= 0;
        fpga_rx_done <= 0;
    end else begin
        fpga_rx_clk_en_d <= fpga_rx_clk_en_r;
        rx_fifo_write_en <= 0;
        if (rx_fifo_write_en) rx_cnt <= rx_cnt + 1'b1;
        if (fpga_data_valid) begin
            fpga_rx_clk_en_r <= 1;
            fpga_rx_addr_r <= 0;
            rx_chunk_bytes <= 0;
            rx_copy_active <= 1;
            fpga_rx_done <= 0;
            if (rx_transaction_complete) begin
                rx_cnt <= 0; rx_bytes_total <= 0;
                rx_pack_data <= 0; rx_pack_bytes <= 0;
            end
            rx_transaction_complete <= 0;
        end else begin
            if (fpga_rx_clk_en_r) begin
                if (fpga_rx_addr_r == total_beats-1)
                    fpga_rx_clk_en_r <= 0;
                fpga_rx_addr_r <= fpga_rx_addr_r + 1'b1;
            end
            if (fpga_rx_clk_en_d) begin
                rx_chunk_bytes <= rx_chunk_bytes + rx_input_bytes;
                rx_bytes_total <= rx_bytes_total + rx_input_bytes;
                if (rx_merge_bytes >= 16) begin
                    rx_fifo_write_en <= 1;
                    rx_fifo_write_data <= rx_merge_data[127:0];
                    rx_pack_data <= rx_merge_data[255:128];
                    rx_pack_bytes <= rx_merge_bytes-16;
                end else begin
                    rx_pack_data <= rx_merge_data[127:0];
                    rx_pack_bytes <= rx_merge_bytes;
                end
            end else if (rx_copy_active && !fpga_rx_clk_en_r && !rx_fifo_write_en) begin
                if ((rx_bytes_total == fpga_ddr3_total_length) && (rx_pack_bytes != 0)) begin
                    // Only the final transaction word is zero padded.
                    rx_fifo_write_en <= 1;
                    rx_fifo_write_data <= rx_pack_data;
                    rx_pack_data <= 0; rx_pack_bytes <= 0;
                end else begin
                    rx_copy_active <= 0;
                    if (rx_bytes_total == fpga_ddr3_total_length)
                        rx_transaction_complete <= 1;
                    else
                        fpga_rx_done <= 1;
                end
            end
            if (rx_transaction_complete && (rx_cnt == dma_total_beats) &&
                fifo_rx_empty && (rx_retired_sync2 != rx_retired_seen))
                fpga_rx_done <= 1;
        end
    end
end
