module ov5640_ddr #(
    parameter DATA_WIDTH = 16,
    parameter AXI_ADDR_WIDTH = 32,
    parameter AXI_LEN_WIDTH  = 32,
    parameter AXI_DATA_WIDTH = 128,
    parameter CAM_DATA_LEN   = 172800, //1280*720*3/16
    parameter DEVICE = "PG"
)(
    input          axi_clk        ,
    input          axi_rst        , 
    input          axi_cam_en     ,      //摄像头启动信号

    input  [AXI_ADDR_WIDTH-1 : 0]      cam_data_addr_1,
    input  [AXI_ADDR_WIDTH-1 : 0]      cam_data_addr_2,
    input  [$clog2(CAM_DATA_LEN) : 0]  cam_data_len   , //以16字节为单位

    input  [DATA_WIDTH-1 : 0]  s_data         /*synthesis PAP_MARK_DEBUG="1"*/,
    input                      s_data_valid   /*synthesis PAP_MARK_DEBUG="1"*/,
    input                      s_hsync        /*synthesis PAP_MARK_DEBUG="1"*/,
    input                      s_vsync        /*synthesis PAP_MARK_DEBUG="1"*/,

    output [AXI_DATA_WIDTH-1 : 0] axi_data       /*synthesis PAP_MARK_DEBUG="1"*/,
    output                        axi_data_valid /*synthesis PAP_MARK_DEBUG="1"*/,
    output                        axi_data_last  /*synthesis PAP_MARK_DEBUG="1"*/, 
    input                         axi_data_ready /*synthesis PAP_MARK_DEBUG="1"*/,

    output [AXI_ADDR_WIDTH-1 : 0]  axi_cmd_addr   /*synthesis PAP_MARK_DEBUG="1"*/,
    output [AXI_LEN_WIDTH-1 : 0]   axi_cmd_len    /*synthesis PAP_MARK_DEBUG="1"*/,
    output                         axi_cmd_valid  /*synthesis PAP_MARK_DEBUG="1"*/,
    input                          axi_cmd_ready  /*synthesis PAP_MARK_DEBUG="1"*/,

    output [1 : 0]   xdma_req       ,
    input  [1 : 0]   xdma_ack        
);

    wire [DATA_WIDTH-1 : 0]  m_data      /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                     m_data_valid/*synthesis PAP_MARK_DEBUG="1"*/;
    wire                     m_hsync     /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                     m_vsync     /*synthesis PAP_MARK_DEBUG="1"*/;

    // [FRTAG 2026-09-14] frame-tag plumbing: the packer stream is detoured through
    // w_* and the ctrl can substitute one counter beat during its DATA_TAG state.
    wire [AXI_DATA_WIDTH-1 : 0] w_data  ;
    wire                        w_valid ;
    wire                        w_last  ;
    wire                        w_ready ;
    wire                        tag_active;
    wire [AXI_DATA_WIDTH-1 : 0] tag_data  ;


ov5640_ddr_w_en #(
    .DATA_WIDTH(DATA_WIDTH)
)
ov5640_ddr_w_en(
    .axi_clk       (axi_clk        ),
    .axi_rst       (axi_rst        ),

    .axi_cam_en    (axi_cam_en),                  //[FREERUN 2026-09-13] no stall: continuous overwrite A1/A2

    .s_data        (s_data         ),
    .s_data_valid  (s_data_valid   ),
    .s_hsync       (s_hsync        ),
    .s_vsync       (s_vsync        ),

    .m_data        (m_data         ),
    .m_data_valid  (m_data_valid   ),
    .m_hsync       (m_hsync        ),
    .m_vsync       (m_vsync        )
);



ov5640_ddr_w #(
    .DATA_WIDTH(DATA_WIDTH),
    .AXI_DATA_WIDTH(AXI_DATA_WIDTH),
    .CAM_DATA_LEN(CAM_DATA_LEN),
    .DEVICE(DEVICE)
) 
ov5640_ddr_w(
    .axi_clk        (axi_clk        ),
    .axi_rst        (axi_rst        ),

    .data_len       (cam_data_len   ), //以16字节为单位

    .s_data         (m_data         ),
    .s_data_valid   (m_data_valid   ),
    .s_hsync        (m_hsync        ),
    .s_vsync        (m_vsync        ),

    .axi_data       (w_data         ),
    .axi_data_valid (w_valid        ),
    .axi_data_last  (w_last         ),
    .axi_data_ready (w_ready        )
);

    // [FRTAG 2026-09-14] frame-tag stream mux: while the ctrl runs its DATA_TAG
    // state it replaces the (idle) camera stream with one AXI_DATA_WIDTH beat
    // carrying the 32-bit frame counter for the second 16-byte command. The
    // camera stream is stalled (not dropped) for those few cycles; its FIFO
    // absorbs the pause. Frame-path behaviour is otherwise bit-identical.
    assign axi_data       = tag_active ? tag_data : w_data;
    assign axi_data_valid = tag_active ? 1'b1    : w_valid;
    assign axi_data_last  = w_last;
    assign w_ready        = axi_data_ready & ~tag_active;



ov5640_ddr_w_ctrl #(
    .AXI_ADDR_WIDTH(AXI_ADDR_WIDTH),
    .AXI_LEN_WIDTH (AXI_LEN_WIDTH ),
    .AXI_DATA_WIDTH(AXI_DATA_WIDTH),
    .CAM_DATA_LEN  (CAM_DATA_LEN  )  //1280*720*3/16
)
ov5640_ddr_w_ctrl(
    .axi_clk        (axi_clk        ),
    .axi_rst        (axi_rst        ),

    .cam_data_addr_1(cam_data_addr_1),
    .cam_data_addr_2(cam_data_addr_2),
    .cam_data_len   (cam_data_len   ),
    
    .s_vsync        (m_vsync        ),

    .axi_data_valid (w_valid        ),
    .axi_data_last  (w_last         ),
    .axi_data_ready (w_ready        ),

    .axi_cmd_addr   (axi_cmd_addr   ),
    .axi_cmd_len    (axi_cmd_len    ),
    .axi_cmd_valid  (axi_cmd_valid  ),
    .axi_cmd_ready  (axi_cmd_ready  ),

    .tag_active     (tag_active     ),
    .tag_data       (tag_data       ),
    .tag_ready      (axi_data_ready ),

    .xdma_req       (xdma_req       ),
    .xdma_ack       (xdma_ack       )
);


    
endmodule