module ov5640 #(
    //DVP�����λ��
    parameter   DATA_WIDTH = 16,
    //I2C
    parameter   SLAVE_ADDR = 7'h3c   ,  //I2C�ӻ���ַ
    parameter   BIT_CTRL   = 1'b1           , //OV5640���ֽڵ�ַΪ16λ  0:8λ 1:16λ
    parameter   CLK_FREQ   = 26'd25_000_000, //[CLKFIX] clk_50m = free_clk 25MHz, //ģ�������ʱ��Ƶ��
    parameter   I2C_FREQ   = 18'd250_000,    //IIC_SCL��ʱ��Ƶ��

    //����
    parameter  H_CMOS_DISP = 11'd1280  , //CMOS�ֱ���--��
    parameter  V_CMOS_DISP = 11'd720   , //CMOS�ֱ���--��	
    parameter  TOTAL_H_PIXEL = 12'd2570, //ˮƽ�����ش�С
    parameter  TOTAL_V_PIXEL = 12'd980 , //��ֱ�����ش�С
    //�忨�豸
    parameter DEVICE = "PG"
)(
    

	input              clk_50m            ,  // Clock i2c�Ĳο�ʱ��
	input              rst_n              ,  // Asynchronous reset active low

    output             ov_rst_n           /*synthesis PAP_MARK_DEBUG="1"*/,  //SCCB�������

	input              cam_pclk           /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos ��������ʱ��
    input              cam_vsync          /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos ��ͬ���ź�
    input              cam_href           /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos ��ͬ���ź�
    input   [7:0]      cam_data           /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos ����
    output             cam_rst_n          /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos ��λ�źţ��͵�ƽ��Ч
    output             cam_pwdn           /*synthesis PAP_MARK_DEBUG="1"*/,  //��Դ����ģʽѡ�� 0������ģʽ 1����Դ����ģʽ
    output             cam_scl            /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos SCCB_SCL��
    inout              cam_sda            /*synthesis PAP_MARK_DEBUG="1"*/,  //cmos SCCB_SDA��    

    input                      video_clk          ,  // ��������ͷ����ʱ��
    input                      video_rst          ,
    output                     video_vsync        /*synthesis PAP_MARK_DEBUG="1"*/,  //֡��Ч�ź�    
    output                     video_hsync        /*synthesis PAP_MARK_DEBUG="1"*/,  //����Ч�ź�  //û��
    output                     video_valid        /*synthesis PAP_MARK_DEBUG="1"*/,  //8bitת16bit������Чʹ���ź�
    output [DATA_WIDTH-1:0]    video_data         /*synthesis PAP_MARK_DEBUG="1"*/,  //��Ч����
    output reg [31:0]         dbg_i2c_status     ,  //[31:16]NACK ops [15:8]ID_H [7:0]ID_L
    output reg [31:0]         dbg_pclk_cnt          ,//free-running pclk counter
    output reg [31:0]         dbg_sys_status        ,//[31:16]exec_cnt [5]sda [4]scl [1]lock [0]rst_n
    output reg [31:0]         dbg_href_raw          ,//raw cam_href rising edges (cam_pclk domain)
    output reg [31:0]         dbg_vsync_raw          //raw cam_vsync rising edges (cam_pclk domain)

    // //�û��ӿ�                              
    // output                      cmos_frame_vsync ,  //֡��Ч�ź�    
    // output                      cmos_frame_href  ,  //����Ч�ź�    //û��
    // output                      cmos_frame_valid ,  //8bitת16bit������Чʹ���ź�
    // output  [DATA_WIDTH-1 : 0]  cmos_frame_data     //��Ч����        
	
);

wire            i2c_dri_clk;
wire            i2c_done;
wire   [7:0]    i2c_data_r;
wire            i2c_exec;
wire   [23:0]   i2c_data;
wire            i2c_rh_wl;
wire            cam_init_done;
wire            i2c_ack;
wire            dri_clk;
wire                    cmos_frame_vsync;
wire                    cmos_frame_href;
wire                    cmos_frame_valid;
wire [DATA_WIDTH-1 : 0] cmos_frame_data;

// wire cam_pclk_bufg/*synthesis PAP_MARK_DEBUG="1"*/;
// GTP_CLKBUFG u_pclk_bufg (
//     .CLKOUT(cam_pclk_bufg),
//     .CLKIN(cam_pclk)
// );

//=========================================================
// ���㼫��λ���ƣ�ֻ��ǰ 5ms ����������
// 50MHz ʱ���£�5ms = 250,000 ������
//=========================================================
reg [$clog2(CLK_FREQ/1000*7) : 0] power_on_cnt; // 18λ�㹻�� 250,000
reg                               i2c_start_en;

always @(posedge clk_50m or negedge rst_n) begin
    if (!rst_n) begin
        power_on_cnt  <= 18'd0;
        i2c_start_en  <= 1'b0; // ǿ�а�ס�ײ�� I2C ģ��
    end 
    else begin
        if (power_on_cnt < CLK_FREQ/1000*7) begin 
            power_on_cnt <= power_on_cnt + 1'b1;
        end 
        else begin
            // 5ms ���ˣ�ͬʱ���֣�
            i2c_start_en  <= 1'b1; // I2C ģ�����ѣ���ʼ���������Լ��� 20ms
        end
    end
end

assign cam_rst_n = i2c_start_en;
assign cam_pwdn  = 1'b0;

//SCCB������ɲ�ץȡ����ͷ
assign ov_rst_n = rst_n & cam_init_done;






// declarations moved above first use for ModelSim compatibility






i2c_dri #(
    .SLAVE_ADDR(SLAVE_ADDR), //I2C�ӻ���ַ
    .CLK_FREQ  (CLK_FREQ  ), //ģ�������ʱ��Ƶ��
    .I2C_FREQ  (I2C_FREQ  )  //IIC_SCL��ʱ��Ƶ��
)
i2c_dri(                                                            
    .clk  (clk_50m)  ,    
    .rst_n(rst_n)    ,   
                                         
    //i2c interface                      
    .i2c_exec   (i2c_exec  ),  //I2C����ִ���ź�
    .bit_ctrl   (BIT_CTRL  ),  //�ֵ�ַλ����(16b/8b)
    .i2c_rh_wl  (i2c_rh_wl ),  //I2C��д�����ź�
    .i2c_addr   (i2c_data[23:8]),  //I2C�����ڵ�ַ
    .i2c_data_w (i2c_data[7:0]),  //I2CҪд������
    .i2c_data_r (i2c_data_r),  //I2C����������
    .i2c_done   (i2c_done  ),  //I2Cһ�β������
    .i2c_ack    (i2c_ack)     ,            //I2CӦ���־ 0:Ӧ�� 1:δӦ��
    .scl        (cam_scl   ),  //I2C��SCLʱ���ź�
    .sda        (cam_sda   ),  //I2C��SDA�ź�
                                       
    //user interface                   
    .dri_clk(dri_clk)       //����I2C����������ʱ��
);



ov5640_i2c_rgb565_cfg #(
    .I2C_FREQ  (I2C_FREQ  )  //IIC_SCL��ʱ��Ƶ��
)
ov5640_i2c_rgb565_cfg(  
    .clk(dri_clk)    ,     //ʱ���ź� SCL��4��Ƶ
    .rst_n(rst_n & i2c_start_en)    ,     //��λ�źţ��͵�ƽ��Ч
    
    .i2c_data_r   (i2c_data_r),  //I2C����������   
    .i2c_done     (i2c_done),    //I2C�Ĵ�����������ź� 
    .cmos_h_pixel (H_CMOS_DISP),
    .cmos_v_pixel (V_CMOS_DISP),
    .total_h_pixel(TOTAL_H_PIXEL), //ˮƽ�����ش�С
    .total_v_pixel(TOTAL_V_PIXEL),  //��ֱ�����ش�С
    .i2c_exec     (i2c_exec),     //I2C����ִ���ź�   
    .i2c_data     (i2c_data),     //I2CҪ���õĵ�ַ������(��16λ��ַ,��8λ����)
    .i2c_rh_wl    (i2c_rh_wl),     //I2C��д�����ź�
    .init_done    (cam_init_done) //��ʼ������ź�
);




// // �� hdmi_loop.v �����ӵ�һ���Ĵ���
// (* IOB = "TRUE" *)reg         cam_vsync_r, cam_href_r;
// (* IOB = "TRUE" *)reg [7:0]   cam_data_r;
// always @(posedge cam_pclk) begin 
//     cam_vsync_r <= cam_vsync;   
//     cam_href_r  <= cam_href;
//     cam_data_r  <= cam_data;
// end


// [DBG] SCCB health: latch first two read bytes (OV5640 ID 0x56,0x40) + NACK op count
reg [3:0] dbg_rd_cnt;
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n) begin
        dbg_rd_cnt     <= 4'd0;
        dbg_i2c_status <= 32'd0;
    end
    else if(i2c_done) begin
        if(i2c_ack) dbg_i2c_status[31:16] <= dbg_i2c_status[31:16] + 16'd1;
        if(i2c_rh_wl && (dbg_rd_cnt < 4'd2)) begin
            dbg_rd_cnt <= dbg_rd_cnt + 4'd1;
            if(dbg_rd_cnt == 4'd0) dbg_i2c_status[15:8] <= i2c_data_r;
            else                   dbg_i2c_status[7:0]  <= i2c_data_r;
        end
    end
end

// [DBG] pclk activity counter (pclk domain, read twice to check delta)
always @(posedge cam_pclk) dbg_pclk_cnt <= dbg_pclk_cnt + 32'd1;
// [PROBE] raw DVP pin edge counters (independent of the CDC FIFO)
reg [2:0] dbg_hr_ff, dbg_vr_ff;
always @(posedge cam_pclk) dbg_hr_ff <= {dbg_hr_ff[1:0], cam_href};
always @(posedge cam_pclk) dbg_vr_ff <= {dbg_vr_ff[1:0], cam_vsync};
always @(posedge cam_pclk) if (dbg_hr_ff[2:1] == 2'b01) dbg_href_raw  <= dbg_href_raw  + 32'd1;
always @(posedge cam_pclk) if (dbg_vr_ff[2:1] == 2'b01) dbg_vsync_raw <= dbg_vsync_raw + 32'd1;
// [DBG] i2c transaction counter + bus level snapshot
wire dbg_sda_lvl = cam_sda;
wire dbg_scl_lvl = cam_scl;
reg [15:0] dbg_exec_cnt;
always @(posedge dri_clk or negedge rst_n) begin
    if(!rst_n) dbg_exec_cnt <= 16'd0;
    else if(i2c_exec) dbg_exec_cnt <= dbg_exec_cnt + 16'd1;
end
always @(posedge dri_clk) dbg_sys_status <= {dbg_exec_cnt, 2'b00, dbg_sda_lvl, dbg_scl_lvl,
                                            1'b0, cam_rst_n};

cmos_capture #(
    .DATA_WIDTH(DATA_WIDTH)
)
cmos_capture(
    .rst_n (ov_rst_n)           ,  //��λ�ź�    
    //����ͷ�ӿ�                           
    .cam_pclk   (cam_pclk) ,   //cmos ��������ʱ��
    .cam_vsync  (cam_vsync),  //cmos ��ͬ���ź�
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


ov5640_cdc #(
    .DATA_WIDTH(DATA_WIDTH),        ////////////////
    .DEVICE(DEVICE)
)
ov5640_cdc(
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
