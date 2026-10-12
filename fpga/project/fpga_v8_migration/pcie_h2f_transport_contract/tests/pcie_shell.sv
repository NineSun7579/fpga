`timescale 1ns/1ps
`ifndef SHELL_MODULE
`define SHELL_MODULE fpga_v8_pango_pcie_top_h2f
`endif
`ifndef CONTROL_MODULE
`define CONTROL_MODULE fpga_v8_pcie_dma_controller_h2f
`endif
// Simulation-only shell. Both DMA controller and MRRS segmentation engine
// are actual RTL. Link/TLP completion delivery and chunk RAM are modeled.
module `SHELL_MODULE #(parameter ADDR_WIDTH=12, MSI_NUM=5) (
    input button_rst_n,perst_n,ref_clk_n,ref_clk_p,
    input [1:0] rxn,rxp,output [1:0] txn,txp,
    output ref_led,pclk_led,smlh_link_up,rdlh_link_up,
    input [MSI_NUM-2:0] i_msi_req,output [MSI_NUM-2:0] o_msi_grant,
    output [31:0] fpga_ddr3_addr,fpga_ddr3_length,fpga_ddr3_total_length,
    input fpga_tx_done,output mwr_tx_busy,input fpga_data_ready,
    output fpga_tx_clk_en,output [ADDR_WIDTH-1:0] fpga_tx_addr,input [127:0] fpga_tx_data,
    input fpga_rx_done,output mrd_rx_busy,input fpga_rx_clk_en,
    input [ADDR_WIDTH-1:0] fpga_rx_addr,output wire [127:0] fpga_rx_data,
    output fifo_pcie_clk,fifo_pcie_rst
);
    assign fifo_pcie_clk=ref_clk_p;
    assign fifo_pcie_rst=!(button_rst_n && perst_n);
    assign {txn,txp}=0;
    assign {ref_led,pclk_led,smlh_link_up,rdlh_link_up}=4'hf;
    assign o_msi_grant=0;
    assign mwr_tx_busy=0;assign fpga_tx_clk_en=0;assign fpga_tx_addr=0;
    reg bar_en=0;reg [ADDR_WIDTH-1:0] bar_addr=0;reg [127:0] bar_data=0;
    wire req32,req64,txreq32,txreq64,msi,ack32,ack64,boundary_error;
    wire [9:0] req_length;wire [63:0] req_addr;
    `CONTROL_MODULE #(.ADDR_WIDTH(ADDR_WIDTH)) controller (
        .clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),
        .i_mwr_tx_busy(~fpga_tx_done),.i_mrd_rx_busy(~fpga_rx_done),.o_fpga_msi(msi),
        .i_bar1_wr_en(bar_en),.i_bar1_wr_addr(bar_addr),.i_bar1_wr_data(bar_data),.i_bar1_wr_byte_en(16'hffff),
        .i_apb_psel(1'b0),.i_apb_paddr(10'b0),.i_apb_pwdata(32'b0),.i_apb_pstrb(4'b0),
        .i_apb_pwrite(1'b0),.i_apb_penable(1'b0),
        .o_mwr32_req(txreq32),.i_mwr32_req_ack(1'b0),.o_mwr64_req(txreq64),.i_mwr64_req_ack(1'b0),
        .o_mrd32_req(req32),.i_mrd32_req_ack(ack32),.o_mrd64_req(req64),.i_mrd64_req_ack(ack64),
        .o_req_length(req_length),.o_req_addr(req_addr),.i_dma_check_result(64'b0),
        .o_cross_4kb_boundary(boundary_error),.o_ddr3_addr(fpga_ddr3_addr),
        .o_ddr3_length(fpga_ddr3_length),.o_ddr3_total_length(fpga_ddr3_total_length)
    );
    reg [2:0] mrrs=0; // Default actual engine setting = 128-byte MRRS.
    integer pcycle=0;
    wire tlp_ready=(pcycle%11!=3 && pcycle%11!=4);
    wire tlp_valid,tlp_last;
    wire [127:0] tlp_data;
    reg completion_valid=0;
    reg [7:0] completion_tag=0;
    ips2l_pcie_dma_mrd_tx_ctrl mrd_engine (
        .clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),.i_cfg_pbus_num(8'b0),.i_cfg_pbus_dev_num(5'b0),
        .i_cfg_max_rd_req_size(mrrs),.i_mrd32_req(req32),.o_mrd32_req_ack(ack32),
        .i_mrd64_req(req64),.o_mrd64_req_ack(ack64),.i_req_length({1'b0,req_length}),
        .i_req_addr(req_addr),.i_cpld_rcv(completion_valid),.i_cpld_tag(completion_tag),
        .i_axis_slave1_trdy(tlp_ready),.o_axis_slave1_tvld(tlp_valid),
        .o_axis_slave1_tdata(tlp_data),.o_axis_slave1_tlast(tlp_last),
        .i_tx_restart(1'b0),.o_mrd_rx_busy(mrd_rx_busy)
    );
    wire [63:0] tlp_address={tlp_data[95:64],tlp_data[127:96]};
    wire [10:0] tlp_dwords=(tlp_data[9:0]==0) ? 11'd1024 : {1'b0,tlp_data[9:0]};
    reg [63:0] host_base=64'h0000000001000000,chunk_base=0;
    reg [31:0] host_word=0;
    reg control_payload=0,ack_seen=0;
    integer fetch_count=0,fetch_bytes=0,illegal_chunks=0,illegal_tlps=0;
    integer j,strict=0;
    // Feed completion payloads through the unchanged actual Pango completion
    // writer and byte-enabled chunk SRAM. Host offsets do not directly select
    // RAM lanes: the actual writer derives them from tag/MRRS and DW validity.
    reg cpl_start=0;
    reg [9:0] cpl_length=0;
    reg [6:0] cpl_low=0;
    reg [11:0] cpl_bytes=0;
    reg [127:0] cpl_data=0;
    reg [3:0] cpl_dw_valid=0;
    reg [7:0] cpl_tag=0;
    wire ram_wr_en;
    wire [ADDR_WIDTH-1:0] ram_wr_addr;
    wire [127:0] ram_wr_data;
    wire [15:0] ram_wr_be;
    ips2l_pcie_dma_rx_cpld_wr_ctrl #(.ADDR_WIDTH(ADDR_WIDTH)) cpl_writer (
        .clk(fifo_pcie_clk),.rst_n(!fifo_pcie_rst),.i_cfg_max_rd_req_size(mrrs),
        .i_cpld_wr_start(cpl_start),.i_cpld_length(cpl_length),.i_cpld_low_addr(cpl_low),
        .i_cpld_byte_cnt(cpl_bytes),.i_cpld_data(cpl_data),.i_cpld_dw_vld(cpl_dw_valid),
        .i_cpld_tag(cpl_tag),.i_bar_hit(2'b10),.i_multicpld_flag(1'b0),
        .o_cpld_wr_en(ram_wr_en),.o_cpld_wr_addr(ram_wr_addr),
        .o_cpld_wr_data(ram_wr_data),.o_cpld_wr_be(ram_wr_be)
    );
    ips2l_pcie_dma_ram chunk_ram (
        .wr_data(ram_wr_data),.wr_addr(ram_wr_addr[8:0]),.wr_en(ram_wr_en),
        .wr_byte_en(ram_wr_be),.wr_clk(fifo_pcie_clk),.wr_rst(fifo_pcie_rst),
        .rd_addr(fpga_rx_addr[8:0]),.rd_data(fpga_rx_data),.rd_clk(fifo_pcie_clk),
        .rd_clk_en(fpga_rx_clk_en),.rd_rst(fifo_pcie_rst)
    );
    reg [63:0] queue_address[0:63];
    reg [10:0] queue_length[0:63];
    reg [7:0] queue_tag[0:63];
    integer queue_wr=0,queue_rd=0;
    reg [63:0] response_address;
    integer response_length,response_index,k;
    function [7:0] host_byte(input [63:0] offset);
        begin
            if(control_payload && offset<4) host_byte=host_word>>(offset*8);
            else host_byte=((offset*37)+11)&255;
        end
    endfunction
    initial if(!$value$plusargs("STRICT=%d",strict)) strict=1;
    always @(negedge fifo_pcie_clk) pcycle=pcycle+1;
    always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
        if(fifo_pcie_rst) begin
            ack_seen<=0;queue_wr=0;
            fetch_count<=0;illegal_chunks<=0;illegal_tlps<=0;
        end else begin
            ack_seen<=ack32 || ack64;
            if((ack32 || ack64) && !ack_seen) begin
                chunk_base<=req_addr;fetch_bytes<=req_length==0 ? 4096 : req_length*4;
                fetch_count<=fetch_count+1;
                if(req_addr[1:0]!=0 || (req_addr[11:0]+(req_length==0 ? 4096 : req_length*4)>4096)) begin
                    illegal_chunks<=illegal_chunks+1;
                    if(strict) $fatal(1,"illegal controller request %016x len=%0d",req_addr,req_length);
                end
            end
            if(tlp_valid && tlp_ready) begin
                if(!tlp_last || tlp_address[1:0]!=0 ||
                   (tlp_address[11:0]+tlp_dwords*4>4096) ||
                   tlp_dwords>(32<<mrrs)) begin
                    illegal_tlps<=illegal_tlps+1;
                    if(strict) $fatal(1,"illegal actual MRD TLP addr=%016x dw=%0d",tlp_address,tlp_dwords);
                end
                if(queue_wr-queue_rd>=64) $fatal(1,"completion queue overflow");
                queue_address[queue_wr%64]=tlp_address;
                queue_length[queue_wr%64]=tlp_dwords;
                queue_tag[queue_wr%64]=tlp_data[47:40];
                queue_wr=queue_wr+1;
            end
            if(strict && ram_wr_en && ram_wr_addr>=256) $fatal(1,"chunk RAM write out of bounds");
            if(strict && fpga_rx_clk_en && fpga_rx_addr>=256) $fatal(1,"chunk RAM read out of bounds");
        end
    end
    // External completer model: one legal completion per actual emitted MRD.
    // Completion receipt reaches the real MRD engine only after all actual
    // SRAM write strobes have drained, as required before RAM consumption.
    initial forever begin
        @(negedge fifo_pcie_clk);
        if(fifo_pcie_rst) begin
            queue_rd=0;cpl_start=0;cpl_dw_valid=0;completion_valid=0;
        end else if(queue_rd<queue_wr) begin
            response_address=queue_address[queue_rd%64];
            response_length=queue_length[queue_rd%64];
            cpl_tag=queue_tag[queue_rd%64];
            cpl_length=response_length;cpl_low=response_address[6:0];cpl_bytes=response_length*4;
            for(response_index=0;response_index<response_length && !fifo_pcie_rst;response_index=response_index+4) begin
                cpl_start=1;
                cpl_dw_valid=(response_length-response_index>=4) ? 4'hf : ((1<<(response_length-response_index))-1);
                cpl_data=0;
                for(k=0;k<16;k=k+1)
                    if(k<(response_length-response_index)*4)
                        cpl_data[k*8+:8]=host_byte(response_address-host_base+response_index*4+k);
                @(negedge fifo_pcie_clk);
            end
            cpl_start=0;cpl_dw_valid=0;cpl_data=0;
            repeat(7) @(negedge fifo_pcie_clk);
            if(!fifo_pcie_rst) begin
                completion_tag=cpl_tag;completion_valid=1;
                @(negedge fifo_pcie_clk);completion_valid=0;queue_rd=queue_rd+1;
            end
        end
    end
    task bar_write(input [11:0] addr,input [31:0] value);
        begin
            @(negedge fifo_pcie_clk);bar_en=1;bar_addr=addr;bar_data={96'b0,value};
            @(negedge fifo_pcie_clk);bar_en=0;
            repeat(4) @(negedge fifo_pcie_clk);
        end
    endtask
    task h2f(input [31:0] target,bytes,word,input [63:0] hostaddr,input bit ctl);
        integer dwords;
        begin
            host_base=hostaddr;host_word=word;control_payload=ctl;
            bar_write(12'h1e0,target);bar_write(12'h110,hostaddr[31:0]);
            bar_write(12'h120,hostaddr[63:32]);bar_write(12'h200,bytes);
            dwords=(bytes>=4096) ? 1024 : (bytes+3)/4;
            bar_write(12'h100,32'h00010000|(dwords&1023));
        end
    endtask
endmodule
