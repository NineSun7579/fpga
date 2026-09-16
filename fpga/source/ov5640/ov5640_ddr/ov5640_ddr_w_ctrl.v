//����CMD����
module ov5640_ddr_w_ctrl #(
    parameter AXI_ADDR_WIDTH = 32,
    parameter AXI_LEN_WIDTH  = 32,
    parameter AXI_DATA_WIDTH = 128,
    parameter CAM_DATA_LEN   = 172800 //1280*720*3/16
)(
    input          axi_clk        ,
    input          axi_rst        ,

    input  [AXI_ADDR_WIDTH-1 : 0]      cam_data_addr_1,
    input  [AXI_ADDR_WIDTH-1 : 0]      cam_data_addr_2,
    input  [$clog2(CAM_DATA_LEN) : 0]  cam_data_len   , //��16�ֽ�Ϊ��λ
    
    input          s_vsync        ,

    input          axi_data_valid ,
    input          axi_data_last  , 
    input          axi_data_ready ,

    output [AXI_ADDR_WIDTH-1 : 0]  axi_cmd_addr   /*synthesis PAP_MARK_DEBUG="1"*/,
    output [AXI_LEN_WIDTH-1 : 0]   axi_cmd_len    /*synthesis PAP_MARK_DEBUG="1"*/,
    output reg                     axi_cmd_valid  /*synthesis PAP_MARK_DEBUG="1"*/,
    input                          axi_cmd_ready  /*synthesis PAP_MARK_DEBUG="1"*/,

    output [1 : 0]   xdma_req       ,
    input  [1 : 0]   xdma_ack       ,

    // [FRTAG 2026-09-14] frame-tag injection. After each frame's last stream beat the
    // FSM issues a SECOND 16-byte AXI command writing a 32-bit frame counter to
    // frame_base + CAM_DATA_LEN*16. The wrapper (ov5640_ddr.v) muxes tag_data onto
    // the data stream while tag_active is high. The transaction must complete:
    // aborting it would leave a pending frame with no new tag for the host.
    output                           tag_active     ,
    output [AXI_DATA_WIDTH-1 : 0]    tag_data       ,
    input                            tag_ready
);

    localparam IDLE      = 3'b001;
    localparam ADDR      = 3'b010;
    localparam DATA      = 3'b100;
    // [FRTAG 2026-09-14] tag states: second (16B) command after the frame completes
    localparam ADDR_TAG  = 3'b011;
    localparam DATA_TAG  = 3'b101;

    reg [2 : 0] curr_state/*synthesis PAP_MARK_DEBUG="1"*/;
    reg [2 : 0] next_state;

    // [FRTAG 2026-09-14] frame-tag declarations (forward, before first use)
    reg                          vsync_pending;
    reg  [AXI_ADDR_WIDTH-1 : 0]  frame_base;
    reg  [31 : 0]                frame_cnt;
    wire [AXI_ADDR_WIDTH-1 : 0]  tag_addr;
    wire                         tag_fire;

    reg [1 : 0] axi_vsync_ff/*synthesis PAP_MARK_DEBUG="1"*/;
    reg axi_vsync_rise/*synthesis PAP_MARK_DEBUG="1"*/;

    
    reg [AXI_ADDR_WIDTH-1 : 0] cmd_addr;


    //״̬��
    always @(posedge axi_clk) begin
        if(axi_rst)begin
            curr_state <= IDLE;
        end
        else begin
            curr_state <= next_state;
        end
    end

    always @(*) begin
        case (curr_state)
            IDLE: begin
                if(vsync_pending)begin
                    next_state = ADDR;
                end
                else begin
                    next_state = IDLE;
                end
            end
            ADDR: begin
                if(axi_cmd_ready & axi_cmd_valid)begin
                    next_state = DATA;
                end
                else begin
                    next_state = ADDR;
                end
            end
            DATA: begin
                if(axi_data_valid & axi_data_ready & axi_data_last)begin
                    next_state = ADDR_TAG;              // [FRTAG] frame complete, go write the tag
                end
                else begin
                    next_state = DATA;
                end
            end
            ADDR_TAG: begin
                if(axi_cmd_ready & axi_cmd_valid)begin
                    next_state = DATA_TAG;
                end
                else begin
                    next_state = ADDR_TAG;
                end
            end
            DATA_TAG: begin
                if(tag_fire)begin
                    next_state = IDLE;
                end
                else begin
                    next_state = DATA_TAG;
                end
            end
            default: begin
                next_state = IDLE;
            end
        endcase
    end
    

    always @(posedge axi_clk) begin
        if(axi_rst)begin
            axi_vsync_ff <= 2'b0;
        end
        else begin
            axi_vsync_ff <= {axi_vsync_ff[0], s_vsync};
        end
    end

    always @(posedge axi_clk) begin
        if(axi_rst)begin
            axi_vsync_rise <= 1'b0;
        end
        else begin
            axi_vsync_rise <= axi_vsync_ff[0] & (~axi_vsync_ff[1]);
        end
    end

    reg w_ping;
    always @(posedge axi_clk) begin
        if(axi_rst)begin
            w_ping <= 1'b0;
        end
        else begin
            if(axi_data_valid & axi_data_ready & axi_data_last)begin
                w_ping <= ~w_ping;
            end
        end
    end


    // [FRTAG 2026-09-14] sticky vsync latch: a vsync pulse arriving while the tag
    // states are running must not be lost (previously a 1-cycle rise pulse).
    always @(posedge axi_clk) begin
        if(axi_rst)begin
            vsync_pending <= 1'b0;
        end
        else if(axi_vsync_rise)begin
            vsync_pending <= 1'b1;
        end
        else if((curr_state == IDLE) && vsync_pending)begin
            vsync_pending <= 1'b0;
        end
    end

    always @(posedge axi_clk) begin
        if(axi_rst)begin
            axi_cmd_valid <= 1'b0;
        end
        else begin
            if((curr_state == IDLE) && vsync_pending)begin
                axi_cmd_valid <= 1'b1;
            end
            else if((curr_state == DATA) && axi_data_valid && axi_data_ready && axi_data_last)begin
                axi_cmd_valid <= 1'b1;      // [FRTAG] frame done -> present the tag command
            end
            else if(axi_cmd_valid & axi_cmd_ready)begin
                axi_cmd_valid <= 1'b0;
            end
        end
    end


    always @(posedge axi_clk) begin
        if(w_ping)begin
            cmd_addr <= cam_data_addr_2; 
        end
        else begin
            cmd_addr <= cam_data_addr_1; 
        end
    end

    assign axi_cmd_addr = (curr_state == ADDR_TAG) ? tag_addr : cmd_addr;
    // [FRTAG 2026-09-14] tag command = one 16-byte beat at frame_base + frame size
    assign axi_cmd_len  = (curr_state == ADDR_TAG) ? 32'd16
                        : {{AXI_LEN_WIDTH-4-$clog2(CAM_DATA_LEN){1'd0}}, cam_data_len, 4'b0};


    // [FRTAG 2026-09-14] frame counter + tag beat generation --------------------
    // frame_base is latched when the FRAME command is accepted (cmd_addr still
    // points at the buffer being written at that moment; w_ping flips later).
    always @(posedge axi_clk) begin
        if(axi_rst)begin
            frame_base <= {AXI_ADDR_WIDTH{1'b0}};
        end
        else if((curr_state == ADDR) && axi_cmd_valid && axi_cmd_ready)begin
            frame_base <= cmd_addr;
        end
    end

    assign tag_addr = frame_base + (CAM_DATA_LEN << 4);

    always @(posedge axi_clk) begin
        if(axi_rst)begin
            frame_cnt <= 32'd0;
        end
        else if((curr_state == DATA) && axi_data_valid && axi_data_ready && axi_data_last)begin
            frame_cnt <= frame_cnt + 32'd1;
        end
    end

    assign tag_active  = (curr_state == DATA_TAG);
    assign tag_data    = {{(AXI_DATA_WIDTH-32){1'b0}}, frame_cnt};
    assign tag_fire    = tag_active & tag_ready;
    // ---------------------------------------------------------------------------


    //XDMAƹ������
    reg [1 : 0] s_xdma_req;
    always @(posedge axi_clk) begin
        if(axi_rst)begin
            s_xdma_req <= 2'b0;
        end
        else begin
            if(axi_data_valid & axi_data_ready & axi_data_last)begin
                if(w_ping)begin
                    s_xdma_req[1] <= 1'b1;
                end
                else begin
                    s_xdma_req[0] <= 1'b1;
                end
            end
            else begin
                if(xdma_ack[0]) begin
                    s_xdma_req[0] <= 1'b0;
                end
                if(xdma_ack[1]) begin
                    s_xdma_req[1] <= 1'b0;
                end
            end
        end
    end

    assign xdma_req = s_xdma_req;




endmodule
