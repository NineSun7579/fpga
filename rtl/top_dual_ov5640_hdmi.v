//****************************************Copyright (c)***********************************//
//ԭ�Ӹ����߽�ѧƽ̨��www.yuanzige.com
//����֧�֣�www.openedv.com
//�Ա����̣�http://openedv.taobao.com
//��ע΢�Ź���ƽ̨΢�źţ�"����ԭ��"����ѻ�ȡZYNQ & FPGA & STM32 & LINUX���ϡ�
//��Ȩ���У�����ؾ���
//Copyright(C) ����ԭ�� 2018-2028
//All rights reserved
//----------------------------------------------------------------------------------------
// File name:           top_dual_ov5640_hdmi
// Last modified Date:  2020/05/04 9:19:08
// Last Version:        V1.0
// Descriptions:        ˫Ŀov5640����ͷHDMi��ʾ
//                      
//----------------------------------------------------------------------------------------
// Created by:          ����ԭ��
// Created date:        2019/05/04 9:19:08
// Version:             V1.0
// Descriptions:        The original version
//
//----------------------------------------------------------------------------------------
//****************************************************************************************//

module top_dual_ov5640_hdmi(    
    input                 sys_clk        ,  //ϵͳʱ��
    input                 sys_rst_n      ,  //ϵͳ��λ���͵�ƽ��Ч
    //����ͷ1�ӿ�                       
    input                 cam_pclk_1     ,  //cmos ��������ʱ��
    input                 cam_vsync_1    ,  //cmos ��ͬ���ź�
    input                 cam_href_1     ,  //cmos ��ͬ���ź�
    input   [7:0]         cam_data_1     ,  //cmos ����
    output                cam_rst_n_1    ,  //cmos ��λ�źţ��͵�ƽ��Ч
    output                cam_pwdn_1     ,  //��Դ����ģʽѡ�� 0������ģʽ 1����Դ����ģʽ
    output                cam_scl_1      ,  //cmos SCCB_SCL��
    inout                 cam_sda_1      ,  //cmos SCCB_SDA��
    //����ͷ2�ӿ�     
    input                 cam_pclk_2     ,  //cmos ��������ʱ��
    input                 cam_vsync_2    ,  //cmos ��ͬ���ź�
    input                 cam_href_2     ,  //cmos ��ͬ���ź�
    input   [7:0]         cam_data_2     ,  //cmos ����
    output                cam_rst_n_2    ,  //cmos ��λ�źţ��͵�ƽ��Ч
    output                cam_pwdn_2     ,  //��Դ����ģʽѡ�� 0������ģʽ 1����Դ����ģʽ
    output                cam_scl_2      ,  //cmos SCCB_SCL��
    inout                 cam_sda_2      ,  //cmos SCCB_SDA��   
    // DDR3                            
    output                mem_rst_n      ,                       
    output                mem_ck         ,
    output                mem_ck_n       ,
    output                mem_cke        ,
    output                mem_ras_n      ,
    output                mem_cas_n      ,
    output                mem_we_n       , 
    output                mem_odt        ,
    output                mem_cs_n       ,
    output  [14:0]        mem_a          ,   
    output  [2:0]         mem_ba         ,   
    inout   [3:0]         mem_dqs        ,
    inout   [3:0]         mem_dqs_n      ,
    inout   [31:0]        mem_dq         ,
    output  [3:0]         mem_dm         ,									   
    //hdmi�ӿ�                            
    output                tmds_clk_p     ,  // TMDS ʱ��ͨ��
    output                tmds_clk_n     ,
    output  [2:0]         tmds_data_p    ,  // TMDS ����ͨ��
    output  [2:0]         tmds_data_n     
);                                 
//parameter define
parameter  V_CMOS_DISP = 13'd1080       ;   // RGB565 active video height
parameter  H_CMOS_DISP = 13'd1920       ;   // RGB565 active video width
parameter  TOTAL_H_PIXEL = 13'd2200     ;   // 1080p60 line timing
parameter  TOTAL_V_PIXEL = 13'd1125     ;   // 1080p60 frame timing
parameter  APP_ADDR_MAX = 28'd2073600   ;   // 1920*1080 pixels, 16-bit address unit
parameter  H_CMOS_DISP_HALF = 13'd960   ;   // one half of the active line


//wire define                          
wire         rst_n                       ;  //ȫ�ָ�λ 							            
wire         cam_init_done               ;  //����ͷ��ʼ�����							    
wire         rdata_req                   ;  //DDR3������ģ���ʹ��
wire  [15:0] rddata                      ;  //DDR3������ģ�������
wire         cmos_frame_valid_1          ;  //����1��Чʹ���ź�
wire  [15:0] wr_data_1                   ;  //DDR3������ģ��д����1
wire         cmos_frame_valid_2          ;  //����2��Чʹ���ź�
wire  [15:0] wr_data_2                   ;  //DDR3������ģ��д����2
wire         init_calib_complete         ;  //DDR3��ʼ�����init_calib_complete
wire         sys_init_done               ;  //ϵͳ��ʼ�����(DDR��ʼ��+����ͷ��ʼ��)
wire         cmos_frame_vsync_1          ;  //���֡1��Ч��ͬ���ź�
wire         cmos_frame_vsync_2          ;  //���֡2��Ч��ͬ���ź�
//PLL
wire         pixel_clk                   ;  //����ʱ��75M
wire         pixel_clk_5x                ;  //5������ʱ��375M
wire         clk_50m                     ;  //output 50M
wire         clk_locked                  ;
//HDMI
wire         video_vs                    ;  //��ͬ���ź�

//*****************************************************
//**                    main code
//*****************************************************

//��ʱ�������������λ�����ź�
assign  rst_n = sys_rst_n & clk_locked;

//ϵͳ��ʼ����ɣ�DDR3��ʼ�����
assign  sys_init_done = init_calib_complete;

//����PLL IP��
pll_clk  u_pll_clk(
    .rst            (~sys_rst_n  ),
    .clkin1         (sys_clk     ),
    .clkout0        (pixel_clk   ), //����ʱ��75M
    .clkout1        (pixel_clk_5x), //5������ʱ��375M
    .clkout2        (clk_50m     ), //output 50M
    .lock           (clk_locked  )
);

//ov5640 ����
ov5640_dri u_ov5640_dri_1(
    .clk               (clk_50m         ),
    .rst_n             (rst_n           ),

    .cam_pclk          (cam_pclk_1      ),
    .cam_vsync         (cam_vsync_1     ),
    .cam_href          (cam_href_1      ),
    .cam_data          (cam_data_1      ),
    .cam_rst_n         (cam_rst_n_1     ),
    .cam_pwdn          (cam_pwdn_1      ),
    .cam_scl           (cam_scl_1       ),
    .cam_sda           (cam_sda_1       ),

    .capture_start     (init_calib_complete),
    .cmos_h_pixel      (H_CMOS_DISP_HALF),
    .cmos_v_pixel      (V_CMOS_DISP     ),
    .total_h_pixel     (TOTAL_H_PIXEL   ),
    .total_v_pixel     (TOTAL_V_PIXEL   ),
    .cmos_frame_vsync  (cmos_frame_vsync_1),
    .cmos_frame_href   (),
    .cmos_frame_valid  (cmos_frame_valid_1),
    .cmos_frame_data   (wr_data_1       )
);   

//ov5640 ����
ov5640_dri u_ov5640_dri_2(
    .clk               (clk_50m),
    .rst_n             (rst_n),

    .cam_pclk          (cam_pclk_2      ),
    .cam_vsync         (cam_vsync_2     ),
    .cam_href          (cam_href_2      ),
    .cam_data          (cam_data_2      ),
    .cam_rst_n         (cam_rst_n_2     ),
    .cam_pwdn          (cam_pwdn_2      ),
    .cam_scl           (cam_scl_2       ),
    .cam_sda           (cam_sda_2       ),
    
    .capture_start     (init_calib_complete),
    .cmos_h_pixel      (H_CMOS_DISP_HALF),
    .cmos_v_pixel      (V_CMOS_DISP     ),
    .total_h_pixel     (TOTAL_H_PIXEL   ),
    .total_v_pixel     (TOTAL_V_PIXEL   ),
    .cmos_frame_vsync  (cmos_frame_vsync_2),
    .cmos_frame_href   (),
    .cmos_frame_valid  (cmos_frame_valid_2),
    .cmos_frame_data   (wr_data_2       )
);    

//DDR3
ddr3_ctrl_top u_ddr3_ctrl_top(
    .clk              (clk_50m          ),
    .rd_clk           (pixel_clk        ),
    .rst_n            (rst_n            ),
    .ddr3_init_done   (init_calib_complete),
    //�û��ӿ�
    .wd_en_1          (cmos_frame_valid_1),
    .wd_en_2          (cmos_frame_valid_2),
    .wd_data_1        (wr_data_1        ),
    .wd_data_2        (wr_data_2        ),
    .wd_clk_1         (cam_pclk_1        ),
    .wd_clk_2         (cam_pclk_2        ),
    .wd_load_1        (cmos_frame_vsync_1),
    .wd_load_2        (cmos_frame_vsync_2),

    .rd_en            (rdata_req        ),
    .rd_data          (rddata           ),
    .rd_load          (video_vs         ),
    .ddr3_pingpang_en (1'b1             ),
    .ddr3_read_valid  (1'b1             ),
    .h_disp           (H_CMOS_DISP      ),
    //��ַ�ӿ�
    .addr_rd_min      (28'b0            ),
    .addr_rd_max      (APP_ADDR_MAX          ),
    .rd_burst_len     (10'd240),
    .addr_wd_min      (28'b0            ),
    .addr_wd_max      (APP_ADDR_MAX          ),
    .wd_burst_len     (10'd240),

    //DDR3 IO�ӿ�
    .mem_rst_n        (mem_rst_n        ),
    .mem_ck           (mem_ck           ),
    .mem_ck_n         (mem_ck_n         ),
    .mem_cke          (mem_cke          ),
    .mem_ras_n        (mem_ras_n        ),
    .mem_cas_n        (mem_cas_n        ),
    .mem_we_n         (mem_we_n         ),
    .mem_odt          (mem_odt          ),
    .mem_cs_n         (mem_cs_n         ),
    .mem_a            (mem_a            ),
    .mem_ba           (mem_ba           ),
    .mem_dqs          (mem_dqs          ),
    .mem_dqs_n        (mem_dqs_n        ),
    .mem_dq           (mem_dq           ),
    .mem_dm           (mem_dm           )
);

//HDMI����ģ��
hdmi_top u_hdmi_top(
    .hdmi_clk         (pixel_clk        ),
    .hdmi_clk_5       (pixel_clk_5x     ),
    .sys_rst_n        (rst_n&sys_init_done),
    //HDMI interface
   .tmds_clk_p       (tmds_clk_p       ),
   .tmds_clk_n       (tmds_clk_n       ),
   .tmds_data_p      (tmds_data_p      ),
   .tmds_data_n      (tmds_data_n      ),
   //user interface
   .rd_data          (rddata           ),
   .rd_en            (rdata_req        ),
   .video_vs         (video_vs         ),
   .pixel_xpos       ( ),
   .pixel_ypos       ( )
);   

endmodule
