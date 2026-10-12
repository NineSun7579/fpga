module frozen_capture_chain(input cam_pclk,cam_vsync,cam_href,input [7:0] cam_data,
input ov_rst_n,cam_rst_n,video_clk,video_rst,
output boundary_fault,
output [15:0] video_data,output video_valid,video_hsync,video_vsync,
output [31:0] dbg_cdc_input,dbg_cdc_output,dbg_cdc_drop,dbg_cdc_seq);
parameter DATA_WIDTH=16; parameter DEVICE="PG";
wire capture_vsync=cam_vsync;
wire cmos_frame_vsync,cmos_frame_href,cmos_frame_valid;
wire [15:0] cmos_frame_data;
cmos_capture #(
    .DATA_WIDTH(DATA_WIDTH)
)
cmos_capture(
    .rst_n (ov_rst_n)           ,  //��λ�ź�    
    //����ͷ�ӿ�                           
    .cam_pclk   (cam_pclk) ,   //cmos ��������ʱ��
    .cam_vsync  (capture_vsync),  //cmos ��ͬ���ź�
    .cam_href   (cam_href) ,  //cmos ��ͬ���ź�
    .cam_data   (cam_data) ,                       
    //�û��ӿ�                              
    .cmos_frame_vsync(cmos_frame_vsync),  //֡��Ч�ź�    
    .cmos_frame_href (cmos_frame_href ),  //����Ч�ź�
    .cmos_frame_valid(cmos_frame_valid),  //������Чʹ���ź�
    .cmos_frame_data (cmos_frame_data )   //��Ч����        
);




// wire [23:0]             cmos_frame_datas;

// assign cmos_frame_datas = {
//     cmos_frame_data[15:11], cmos_frame_data[15:13], // R: 5λ + ��3λ
//     cmos_frame_data[10:5] , cmos_frame_data[10:9] , // G: 6λ + ��2λ
//     cmos_frame_data[4:0]  , cmos_frame_data[4:2]    // B: 5λ + ��3λ
// };




reg         cam_vsync_r, cam_href_r;
reg [7:0]   cam_data_r;

reg [DATA_WIDTH-1 : 0] cmos_frame_data_r;
reg cmos_frame_valid_r, cmos_frame_href_r, cmos_frame_vsync_r;
always @(negedge cam_pclk) begin 
    cmos_frame_data_r <= cmos_frame_data ; 
    cmos_frame_valid_r <= cmos_frame_valid;
    cmos_frame_href_r <= cmos_frame_href ;
    cmos_frame_vsync_r <= cmos_frame_vsync;
end


cdc_recovery #(
    .DATA_WIDTH(DATA_WIDTH),        ////////////////
    .DEVICE(DEVICE)
)
ov5640_cdc(
    .dbg_cdc_input(dbg_cdc_input),
    .dbg_cdc_output(dbg_cdc_output),
    .dbg_cdc_drop(dbg_cdc_drop),
    .dbg_cdc_seq(dbg_cdc_seq),
    .system_reset(video_rst),.boundary_fault(boundary_fault),
    .cam_clk(cam_pclk),
    .cam_rst(!cam_rst_n),

    .s_data (cmos_frame_data_r )    , //////////////
    .s_valid(cmos_frame_valid_r)    ,
    .s_hsync(cmos_frame_href_r )    ,
    .s_vsync(cmos_frame_vsync_r)    ,

    .video_clk  (video_clk  ), 
    .video_rst  (video_rst  ),
    .video_data (video_data ),
    .video_valid(video_valid),
    .video_hsync(video_hsync),
    .video_vsync(video_vsync) 
);


endmodule
