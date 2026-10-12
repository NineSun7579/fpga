//ov5640дʹ�ܿ��ƺ�д��ַ����
module ov5640_reg #(
    parameter BASE_ADDR = 32'h2000_0000,
    parameter [31:0] CAM_ADDR_1_DEF = 32'h0080_0000,
    parameter [31:0] CAM_ADDR_2_DEF = 32'h00A0_0000,
    parameter        CAM_EN_DEF     = 1'b1,
    parameter [7:0]  DLY_STEP_DEF   = 8'd40,
    // parameter AXI_REG_WIDTH = 32,
    parameter AXI_ADDR_WIDTH = 32
) (
    input             clk                   ,
    input             rst                   ,

    input                             s_axi_awvalid         ,
    output                            s_axi_awready         ,
    input  [AXI_ADDR_WIDTH-1 : 0]     s_axi_awaddr          ,

    input                             s_axi_wvalid          ,
    output                            s_axi_wready          ,
    input  [AXI_ADDR_WIDTH-1 : 0]     s_axi_wdata           ,
    input  [AXI_ADDR_WIDTH/8-1 : 0]   s_axi_wstrb           ,

    output                            s_axi_bvalid          ,
    input                             s_axi_bready          ,
    output [ 1 : 0]                   s_axi_bresp           ,

    input                             s_axi_arvalid         ,
    output                            s_axi_arready         ,
    input  [AXI_ADDR_WIDTH-1 : 0]     s_axi_araddr          ,

    output                            s_axi_rvalid          ,
    input                             s_axi_rready          ,
    output [AXI_ADDR_WIDTH-1 : 0]     s_axi_rdata           ,
    output [ 1 : 0]                   s_axi_rresp           ,


    output reg [AXI_ADDR_WIDTH-1 : 0] cam_addr_1            ,
    output reg [AXI_ADDR_WIDTH-1 : 0] cam_addr_2            ,        
    output reg [1 : 0]                xdma_ack              ,
    output reg                        cam_en                        ,
    output reg [7:0]                  dly_step                      ,
    input [31:0] dbg_cdc_input,
    input [31:0] dbg_cdc_output,
    input [31:0] dbg_cdc_drop,
    input [31:0] dbg_cdc_seq,
    input [31:0] dbg_fault_snapshot,
    input [31:0] dbg_reject_counts,
    input [31:0] dbg_input_pixels,
    input [31:0] dbg_vsync_widths,
    input  [31:0]                     dbg_cam_words         ,
    input  [31:0]                     dbg_vsyncs        ,
    input  [31:0]                     dbg_hsyncs        ,
    input  [31:0]                     dbg_href_raw      ,
    input  [31:0]                     dbg_vsync_raw     ,
    input  [31:0]                     dbg_beat_cnt      ,
    input  [31:0]                     dbg_beat_last     ,
    input  [31:0]                     dbg_cmd_cnt       ,
    input  [31:0]                     dbg_axi_sticky    ,
    input  [31:0]                     dbg_axi_stat      ,
    input  [31:0]                     dbg_b_cnt         ,
    input  [31:0]                     dbg_aw_cnt        ,
    input  [31:0]                     dbg_w_cnt         ,
    input  [31:0]                     dbg_axi_cnt       ,
    input  [31:0]                     dbg_zdin          ,
    input  [31:0]                     dbg_zout          ,
    input  [31:0]                     dbg_axi_num       ,
    input  [31:0]                     dbg_state         ,
    input  [31:0]                     dbg_last_cnt      ,
    input  [31:0]                     dbg_wd_cnt        ,
    input  [1:0]                      dbg_xdma_req        ,
    input  [31:0]                     dbg_i2c_status      ,
    input  [31:0]                     dbg_pclk_cnt        ,
    input  [31:0]                     dbg_sys_status      ,
    input  [31:0]                     dbg_clk_status,

    // [PT 2026-09-26] host SCCB passthrough (video_clk domain; CDC in ov5640_top)
    output reg                        pt_req_toggle,
    output reg  [15:0]                pt_addr,
    output reg  [ 7:0]                pt_wdata,
    output reg                        pt_rw,
    input       [ 7:0]                pt_rdata,
    input                             pt_ack,
    input                             pt_done_toggle
);

//�Ĵ�����ַ
localparam REG_ACK       = BASE_ADDR + 32'h00;
localparam REG_CAM_EN    = BASE_ADDR + 32'h40;
// [CAM3DLY 2026-09-27] per-camera DVP sampling delay step (port mode).
// Write-only here: offset 0x30 still READS the CAM_WORDS debug counter, so a
// write to it was previously a no-op.  Lets the phase be swept on-board.
localparam REG_DLY_STEP  = BASE_ADDR + 32'h30;
localparam REG_CAM_ADDR_1= BASE_ADDR + 32'h80;
localparam REG_CAM_ADDR_2= BASE_ADDR + 32'hc0;
// [PROBE 2026-09-18] every offset is 16-byte aligned: the PCIe M01 read
// path ignores addr[3:0], so only *0 offsets are individually readable.
localparam REG_DBG_PCLK_CNT  = BASE_ADDR + 32'h10;
localparam REG_DBG_VSYNCS    = BASE_ADDR + 32'h20;
localparam REG_DBG_CAM_WORDS = BASE_ADDR + 32'h30;
localparam REG_DBG_AXI_STICKY= BASE_ADDR + 32'h50;
localparam REG_DBG_I2C_ID    = BASE_ADDR + 32'h60;
localparam REG_DBG_SYS       = BASE_ADDR + 32'h70;
localparam REG_DBG_HREF_RAW  = BASE_ADDR + 32'h90;
localparam REG_DBG_BEAT_CNT  = BASE_ADDR + 32'ha0;
localparam REG_DBG_BEAT_LAST = BASE_ADDR + 32'hf0;
localparam REG_DBG_XDMA_REQ  = BASE_ADDR + 32'hb0;
localparam REG_DBG_VSYNC_RAW = BASE_ADDR + 32'he0;
localparam REG_DBG_AXI_NOW   = BASE_ADDR + 32'hd0;
// [ZDIAG 2026-09-18] 0x50/0x90 repurposed from the old axi_sticky/href_raw
// probes (kept inside the addr[9:8]=00 CAM1 segment; 0x100+ routes to prep).
localparam REG_DBG_ZDIN      = BASE_ADDR + 32'h50;
localparam REG_DBG_ZOUT      = BASE_ADDR + 32'h90;
// [PT 2026-09-26] host SCCB passthrough (cam3 page: BASE+0x100..0x12F)
localparam REG_I2C_CMD  = BASE_ADDR + 32'h100;
localparam REG_I2C_RD   = BASE_ADDR + 32'h110;
localparam REG_I2C_STAT = BASE_ADDR + 32'h120;

    reg bvalid        ;
    reg data_out_valid;

    reg rvalid;
    reg [AXI_ADDR_WIDTH-1 : 0] rdata ;

    //XDAMӦ��
    always @(posedge clk) begin
        if(rst)begin
            xdma_ack <= 2'b0;
        end
        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_ACK))begin
            xdma_ack <= s_axi_wdata[1 : 0];
        end
        else begin
            xdma_ack <= 2'b0;
        end
    end

    //����ͷʹ��
    always @(posedge clk) begin
        if(rst)begin
            cam_en <= CAM_EN_DEF;
        end
        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_CAM_EN))begin
            cam_en <= s_axi_wdata[0];
        end
    end

    // [CAM3DLY 2026-09-27] runtime DVP sampling delay for this camera.
    always @(posedge clk) begin
        if(rst)begin
            dly_step <= DLY_STEP_DEF;
        end
        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_DLY_STEP))begin
            dly_step <= s_axi_wdata[7:0];
        end
    end

    //ͼƬ��ַ1
    always @(posedge clk) begin
        if(rst)begin
            cam_addr_1 <= CAM_ADDR_1_DEF;
        end
        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_CAM_ADDR_1))begin
            cam_addr_1 <= s_axi_wdata;
        end
    end

    //ͼƬ��ַ2
    always @(posedge clk) begin
        if(rst)begin
            cam_addr_2 <= CAM_ADDR_2_DEF;
        end
        else if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) && (s_axi_awaddr == REG_CAM_ADDR_2))begin
            cam_addr_2 <= s_axi_wdata;
        end
    end

    // [PT 2026-09-26] host SCCB passthrough command + result latch.
    //   Any write to REG_I2C_CMD issues one SCCB transaction (after sensor
    //   init). done/ack/rdata are latched back for polling reads.
    reg        pt_done_lat;
    reg [ 7:0] pt_rdata_lat;
    reg        pt_ack_lat;
    reg        pt_done_d;
    always @(posedge clk) begin
        if(rst) begin
            pt_addr       <= 16'd0;
            pt_wdata      <= 8'd0;
            pt_rw         <= 1'b0;
            pt_req_toggle <= 1'b0;
            pt_done_lat   <= 1'b0;
            pt_rdata_lat  <= 8'd0;
            pt_ack_lat    <= 1'b0;
            pt_done_d     <= 1'b0;
        end
        else begin
            pt_done_d <= pt_done_toggle;
            if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready) &&
               (s_axi_awaddr == REG_I2C_CMD)) begin
                pt_addr       <= s_axi_wdata[23:8];
                pt_wdata      <= s_axi_wdata[7:0];
                pt_rw         <= s_axi_wdata[24];
                pt_req_toggle <= ~pt_req_toggle;
                pt_done_lat   <= 1'b0;
            end
            if(pt_done_toggle ^ pt_done_d) begin
                pt_rdata_lat <= pt_rdata;
                pt_ack_lat   <= pt_ack;
                pt_done_lat  <= 1'b1;
            end
        end
    end

    //��Ϊ��һ�����Ĵ��������������û���ж϶���ַ
    reg r_state;
    always @(posedge clk) begin
        if(rst)begin
            r_state <= 1'b0;
        end
        else begin
            if(s_axi_arvalid & s_axi_arready) begin
                r_state <= 1'b1;
            end
            else if(s_axi_rvalid & s_axi_rready) begin
                r_state <= 1'b0;
            end
        end
    end

    always @(posedge clk) begin
        if(rst)begin
            data_out_valid <= 1'b0;
        end
        else begin
            if(s_axi_arvalid & s_axi_arready)begin
                data_out_valid <= 1'b1;
            end
            else begin
                data_out_valid <= 1'b0;
            end
        end
    end


    // ����һ���ݴ����ַ�ļĴ���
    // P1: register priority one-hot at the original AR capture edge.
    reg [22:0] read_select;
    always @(posedge clk) begin
        if (s_axi_arvalid & s_axi_arready) begin
            case (s_axi_araddr)
                REG_ACK: read_select <= 23'h000001;
                REG_CAM_EN: read_select <= 23'h000002;
                REG_CAM_ADDR_1: read_select <= 23'h000004;
                REG_CAM_ADDR_2: read_select <= 23'h000008;
                BASE_ADDR + 32'h190: read_select <= 23'h000010;
                BASE_ADDR + 32'h1a0: read_select <= 23'h000020;
                BASE_ADDR + 32'h1b0: read_select <= 23'h000040;
                BASE_ADDR + 32'h1c0: read_select <= 23'h000080;
                REG_DBG_CAM_WORDS: read_select <= 23'h000100;
                REG_DBG_VSYNCS: read_select <= 23'h000200;
                REG_DBG_ZDIN: read_select <= 23'h000400;
                REG_DBG_ZOUT: read_select <= 23'h000800;
                REG_DBG_BEAT_CNT: read_select <= 23'h001000;
                REG_DBG_BEAT_LAST: read_select <= 23'h002000;
                REG_DBG_XDMA_REQ: read_select <= 23'h004000;
                REG_DBG_VSYNC_RAW: read_select <= 23'h008000;
                REG_DBG_I2C_ID: read_select <= 23'h010000;
                REG_DBG_PCLK_CNT: read_select <= 23'h020000;
                REG_DBG_SYS: read_select <= 23'h040000;
                REG_DBG_AXI_NOW: read_select <= 23'h080000;
                REG_I2C_RD: read_select <= 23'h100000;
                REG_I2C_STAT: read_select <= 23'h200000;
                default: read_select <= 23'h400000;
            endcase
        end
    end

    // Sized wires retain original assignment extension/truncation.
    // Values remain live until the original data_out_valid edge.
    wire [AXI_ADDR_WIDTH-1:0] read_value_0 = dbg_fault_snapshot;
    wire [AXI_ADDR_WIDTH-1:0] read_value_1 = {{AXI_ADDR_WIDTH-1{1'b0}}, cam_en};
    wire [AXI_ADDR_WIDTH-1:0] read_value_2 = cam_addr_1;
    wire [AXI_ADDR_WIDTH-1:0] read_value_3 = cam_addr_2;
    wire [AXI_ADDR_WIDTH-1:0] read_value_4 = dbg_cdc_input;
    wire [AXI_ADDR_WIDTH-1:0] read_value_5 = dbg_cdc_output;
    wire [AXI_ADDR_WIDTH-1:0] read_value_6 = dbg_cdc_drop;
    wire [AXI_ADDR_WIDTH-1:0] read_value_7 = dbg_cdc_seq;
    wire [AXI_ADDR_WIDTH-1:0] read_value_8 = dbg_input_pixels;
    wire [AXI_ADDR_WIDTH-1:0] read_value_9 = dbg_vsyncs;
    wire [AXI_ADDR_WIDTH-1:0] read_value_10 = dbg_vsync_widths;
    wire [AXI_ADDR_WIDTH-1:0] read_value_11 = dbg_href_raw;
    wire [AXI_ADDR_WIDTH-1:0] read_value_12 = dbg_reject_counts;
    wire [AXI_ADDR_WIDTH-1:0] read_value_13 = dbg_last_cnt;
    wire [AXI_ADDR_WIDTH-1:0] read_value_14 = {{(AXI_ADDR_WIDTH-2){1'b0}}, dbg_xdma_req};
    wire [AXI_ADDR_WIDTH-1:0] read_value_15 = dbg_vsync_raw;
    wire [AXI_ADDR_WIDTH-1:0] read_value_16 = {dbg_wd_cnt[7:0], dbg_state[7:0], dbg_cmd_cnt[15:0]};
    wire [AXI_ADDR_WIDTH-1:0] read_value_17 = dbg_pclk_cnt;
    wire [AXI_ADDR_WIDTH-1:0] read_value_18 = {dbg_b_cnt[15:0], dbg_aw_cnt[15:0]};
    wire [AXI_ADDR_WIDTH-1:0] read_value_19 = dbg_sys_status;
    wire [AXI_ADDR_WIDTH-1:0] read_value_20 = {{(AXI_ADDR_WIDTH-8){1'b0}}, pt_rdata_lat};
    wire [AXI_ADDR_WIDTH-1:0] read_value_21 = {{(AXI_ADDR_WIDTH-2){1'b0}}, pt_done_lat, pt_ack_lat};
    wire [AXI_ADDR_WIDTH-1:0] read_value_22 = {AXI_ADDR_WIDTH{1'b1}};
    wire [AXI_ADDR_WIDTH-1:0] read_mux =
        ({AXI_ADDR_WIDTH{read_select[0]}} & read_value_0) |
        ({AXI_ADDR_WIDTH{read_select[1]}} & read_value_1) |
        ({AXI_ADDR_WIDTH{read_select[2]}} & read_value_2) |
        ({AXI_ADDR_WIDTH{read_select[3]}} & read_value_3) |
        ({AXI_ADDR_WIDTH{read_select[4]}} & read_value_4) |
        ({AXI_ADDR_WIDTH{read_select[5]}} & read_value_5) |
        ({AXI_ADDR_WIDTH{read_select[6]}} & read_value_6) |
        ({AXI_ADDR_WIDTH{read_select[7]}} & read_value_7) |
        ({AXI_ADDR_WIDTH{read_select[8]}} & read_value_8) |
        ({AXI_ADDR_WIDTH{read_select[9]}} & read_value_9) |
        ({AXI_ADDR_WIDTH{read_select[10]}} & read_value_10) |
        ({AXI_ADDR_WIDTH{read_select[11]}} & read_value_11) |
        ({AXI_ADDR_WIDTH{read_select[12]}} & read_value_12) |
        ({AXI_ADDR_WIDTH{read_select[13]}} & read_value_13) |
        ({AXI_ADDR_WIDTH{read_select[14]}} & read_value_14) |
        ({AXI_ADDR_WIDTH{read_select[15]}} & read_value_15) |
        ({AXI_ADDR_WIDTH{read_select[16]}} & read_value_16) |
        ({AXI_ADDR_WIDTH{read_select[17]}} & read_value_17) |
        ({AXI_ADDR_WIDTH{read_select[18]}} & read_value_18) |
        ({AXI_ADDR_WIDTH{read_select[19]}} & read_value_19) |
        ({AXI_ADDR_WIDTH{read_select[20]}} & read_value_20) |
        ({AXI_ADDR_WIDTH{read_select[21]}} & read_value_21) |
        ({AXI_ADDR_WIDTH{read_select[22]}} & read_value_22);



    always @(posedge clk) begin
        if(rst)begin
            rvalid <= 1'b0;
            rdata  <= {AXI_ADDR_WIDTH{1'b0}}; // ע�⣺rdata λ��Ӧ���� 32������ 1
        end
        else begin
            if(data_out_valid) begin
                rvalid <= 1'b1;
                // ���ݸղ�����Ķ���ַ�����ض�Ӧ�Ĵ�������ʵֵ
                rdata <= read_mux;
            end
            else if(s_axi_rvalid & s_axi_rready)begin
                rvalid <= 1'b0;
                // rdata ���ֲ��伴�ɣ�ֱ����һ�ζ�����
            end
        end
    end


    always @(posedge clk) begin
        if(rst)begin
            bvalid <= 1'b0;
        end
        else begin
            if((s_axi_awvalid & s_axi_awready) && (s_axi_wvalid & s_axi_wready))begin
                bvalid <= 1'b1;
            end
            else if(bvalid & s_axi_bready)begin
                bvalid <= 1'b0;
            end
        end
    end

    assign s_axi_awready = s_axi_awvalid & s_axi_wvalid;
    assign s_axi_wready  = s_axi_awvalid & s_axi_wvalid;
    
    assign s_axi_arready = s_axi_arvalid & (r_state == 1'b0);
    assign s_axi_rvalid  = rvalid        ;
    assign s_axi_rdata   = rdata         ;
    assign s_axi_rresp   = 2'b00         ;
    
    assign s_axi_bvalid = bvalid;
    assign s_axi_bresp  = 2'b00 ;


endmodule
