`timescale 1ns/1ps
// Replaces ONLY PCIe hard IP + incoming BAR writes. Real controller, real MWr
// packetizer and real prefetch reader stay in this simulation. AXIS_SLAVE_NUM=3
// uses direct slave2 MWr, as routed production does. Not a hard-IP ordering model.
module fpga_v8_pango_pcie_top_h2f_rfg01 #(
    parameter ADDR_WIDTH=12, MSI_NUM=5
) (
    input i_admit, button_rst_n, perst_n, ref_clk_n, ref_clk_p,
    input [1:0] rxn,rxp, output [1:0] txn,txp,
    output ref_led,pclk_led,smlh_link_up,rdlh_link_up,
    input [MSI_NUM-2:0] i_msi_req, output [MSI_NUM-2:0] o_msi_grant,
    output [31:0] fpga_ddr3_addr,fpga_ddr3_length,fpga_ddr3_total_length,
    input fpga_tx_done, output mwr_tx_busy, input fpga_data_ready,
    output fpga_tx_clk_en, output [ADDR_WIDTH-1:0] fpga_tx_addr,
    input [127:0] fpga_tx_data,
    input fpga_rx_done, output mrd_rx_busy,
    input fpga_rx_clk_en, input [ADDR_WIDTH-1:0] fpga_rx_addr,
    output [127:0] fpga_rx_data,
    output fifo_pcie_clk,fifo_pcie_rst
);
    assign fifo_pcie_clk=ref_clk_p;
    assign fifo_pcie_rst=!(button_rst_n && perst_n);
    assign {txn,txp}=0;
    assign {ref_led,pclk_led,smlh_link_up,rdlh_link_up}=4'hf;
    assign o_msi_grant=0;
    assign mrd_rx_busy=0;
    assign fpga_rx_data=0;
    reg bar_en=0;
    reg [ADDR_WIDTH-1:0] bar_addr=0;
    reg [127:0] bar_data=0;
    wire req32,req64,ack32,ack64,msi;
    wire [9:0] req_length;
    wire [63:0] req_addr;
`ifdef CANDIDATE
    wire completion_busy=mwr_tx_busy | ~fpga_tx_done;
    fpga_v8_pcie_dma_controller_h2f_rfg01_dcb01_candidate #(.ADDR_WIDTH(ADDR_WIDTH)) controller (
`else
    wire completion_busy=~fpga_tx_done;
    fpga_v8_pcie_dma_controller_h2f_rfg01_dcb01_original #(.ADDR_WIDTH(ADDR_WIDTH)) controller (
`endif
        .i_admit(i_admit),.clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),
        .i_mwr_tx_busy(completion_busy),.i_mrd_rx_busy(~fpga_rx_done),
        .o_fpga_msi(msi),.i_bar1_wr_en(bar_en),.i_bar1_wr_addr(bar_addr),
        .i_bar1_wr_data(bar_data),.i_bar1_wr_byte_en(16'hffff),
        .i_apb_psel(1'b0),.i_apb_paddr(10'b0),.i_apb_pwdata(32'b0),
        .i_apb_pstrb(4'b0),.i_apb_pwrite(1'b0),.i_apb_penable(1'b0),
        .o_mwr32_req(req32),.i_mwr32_req_ack(ack32),
        .o_mwr64_req(req64),.i_mwr64_req_ack(ack64),
        .i_mrd32_req_ack(1'b0),.i_mrd64_req_ack(1'b0),
        .o_req_length(req_length),.o_req_addr(req_addr),.i_dma_check_result(64'b0),
        .o_ddr3_addr(fpga_ddr3_addr),.o_ddr3_length(fpga_ddr3_length),
        .o_ddr3_total_length(fpga_ddr3_total_length)
    );
    wire rd_en, gen_start, last_data, tx_hold, tlp_tx;
    wire [10:0] rd_length;
    wire [127:0] rd_data;
    reg ready=1;
    wire valid,last,user;
    wire [127:0] data;
    ips2l_pcie_dma_mwr_tx_ctrl packetizer (
        .clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),
        .i_cfg_pbus_num(8'h01),.i_cfg_pbus_dev_num(5'b0),.i_cfg_max_payload_size(3'b0),
        .i_user_define_data_flag(1'b0),.i_mwr32_req(req32),.o_mwr32_req_ack(ack32),
        .i_mwr64_req(req64),.o_mwr64_req_ack(ack64),
        .i_req_length({1'b0,req_length}),.i_req_addr(req_addr),.i_req_data(32'b0),
        .o_rd_en(rd_en),.o_rd_length(rd_length),.i_gen_tlp_start(gen_start),
        .i_rd_data(rd_data),.i_last_data(last_data),.i_axis_slave2_trdy(ready),
        .o_axis_slave2_tvld(valid),.o_axis_slave2_tdata(data),
        .o_axis_slave2_tlast(last),.o_axis_slave2_tuser(user),
        .o_mwr_tx_busy(mwr_tx_busy),.o_mwr_tx_hold(tx_hold),.o_mwr_tlp_tx(tlp_tx),
        .i_tx_restart(1'b0)
    );
    ips2l_pcie_dma_tx_mwr_rd_ctrl #(.ADDR_WIDTH(ADDR_WIDTH)) reader (
        .clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),.i_data_ready(fpga_data_ready),
        .i_rd_en(rd_en),.i_rd_length(rd_length),.i_mwr_tx_busy(mwr_tx_busy),
        .i_mwr_tx_hold(tx_hold),.i_mwr_tlp_tx(tlp_tx),
        .o_gen_tlp_start(gen_start),.o_rd_data(rd_data),.o_last_data(last_data),
        .o_bar_rd_clk_en(fpga_tx_clk_en),.o_bar_rd_addr(fpga_tx_addr),
        .i_bar_rd_data(fpga_tx_data)
    );
    task bar_write(input [11:0] addr,input [31:0] value);
        @(negedge fifo_pcie_clk);bar_en=1;bar_addr=addr;bar_data={96'b0,value};
        @(negedge fifo_pcie_clk);bar_en=0;
        repeat(4) @(negedge fifo_pcie_clk);
    endtask
    task f2h(input [31:0] target,bytes,hostaddr);
        bar_write(12'h1e0,target);bar_write(12'h110,hostaddr);bar_write(12'h120,0);
        bar_write(12'h200,bytes);
        bar_write(12'h100,32'h01010000 | ((bytes>=4096 ? 1024 : bytes/4)&1023));
    endtask
endmodule
