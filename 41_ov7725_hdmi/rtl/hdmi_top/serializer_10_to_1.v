//****************************************Copyright (c)***********************************//
//原子哥在线教学平台：www.yuanzige.com
//技术支持：www.openedv.com
//淘宝店铺：http://openedv.taobao.com
//关注微信公众平台微信号："正点原子"，免费获取ZYNQ & FPGA & STM32 & LINUX资料。
//版权所有，盗版必究。
//Copyright(C) 正点原子 2018-2028
//All rights reserved
//----------------------------------------------------------------------------------------
// File name:           serializer_10_to_1
// Last modified Date:  2021/4/7 9:30:00
// Last Version:        V1.1
// Descriptions:        用于实现10:1并串转换
//----------------------------------------------------------------------------------------
// Created by:          正点原子
// Created date:        2021/4/7 9:30:00
// Version:             V1.0
// Descriptions:        The original version
//
//----------------------------------------------------------------------------------------
//****************************************************************************************//

`timescale 1ns / 1ps

module serializer_10_to_1(
    input           serial_clk_5x,      // 输入串行高速数据时钟
    input           serial_clk,         // 输入串行低速数据时钟
    input   [9:0]   paralell_data,      // 输入并行数据
    input           reset_n,

    output          serial_data_p,      // 输出串行差分数据P
    output          serial_data_n       // 输出串行差分数据N
    );
   
GTP_OSERDES_E2 #
(
. GRS_EN        ( "TRUE"       ),
. OSERDES_MODE  ( "DDR10TO1"   ),
. TSERDES_EN    ( "FALSE"      ),
. UPD0_SHIFT_EN ( "FALSE"      ), 
. UPD1_SHIFT_EN ( "FALSE"      ), 
. INIT_SET      ( 2'b00        ), 
. GRS_TYPE_DQ   ( "RESET"      ), 
. LRS_TYPE_DQ0  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ1  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ2  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ3  ( "ASYNC_RESET"), 
. GRS_TYPE_TQ   ( "RESET"      ), 
. LRS_TYPE_TQ0  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ1  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ2  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ3  ( "ASYNC_RESET"), 
. TRI_EN        ( "FALSE"      ),
. TBYTE_EN      ( "FALSE"      ), 
. MIPI_EN       ( "FALSE"      ), 
. OCASCADE_EN   ( "FALSE"      )    //"FALSE","TRUE"
) 
GTP_OSERDES_E2_data_master (
. RST           ( 0     ),
. OCE           ( 1'b1           ),
. TCE           ( 1'b0           ),
. OCLKDIV       ( serial_clk   ),
. SERCLK        ( serial_clk_5x     ),
. OCLK          ( serial_clk_5x     ),
. MIPI_CTRL     (                ),
. UPD0_SHIFT    ( 1'b0           ),
. UPD1_SHIFT    ( 1'b0           ),
. OSHIFTIN0     ( OSHIFTIN0   ),
. OSHIFTIN1     ( OSHIFTIN1   ),
. DI            ( paralell_data[7:0] ),
. TI            (                ),
. TBYTE_IN      (                ),
. OSHIFTOUT0    (                ),
. OSHIFTOUT1    (                ),
. DO            ( tx_data_out ),
. TQ            (                )
);


GTP_OSERDES_E2 #
(
. GRS_EN        ( "TRUE"       ),
. OSERDES_MODE  ( "DDR10TO1"   ),
. TSERDES_EN    ( "FALSE"      ),
. UPD0_SHIFT_EN ( "FALSE"      ), 
. UPD1_SHIFT_EN ( "FALSE"      ), 
. INIT_SET      ( 2'b00        ), 
. GRS_TYPE_DQ   ( "RESET"      ), 
. LRS_TYPE_DQ0  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ1  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ2  ( "ASYNC_RESET"), 
. LRS_TYPE_DQ3  ( "ASYNC_RESET"), 
. GRS_TYPE_TQ   ( "RESET"      ), 
. LRS_TYPE_TQ0  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ1  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ2  ( "ASYNC_RESET"), 
. LRS_TYPE_TQ3  ( "ASYNC_RESET"), 
. TRI_EN        ( "FALSE"      ),
. TBYTE_EN      ( "FALSE"      ), 
. MIPI_EN       ( "FALSE"      ), 
. OCASCADE_EN   ( "TRUE"       )    //"FALSE","TRUE"
) 
GTP_OSERDES_E2_data_slave
(
. RST           ( 0    ),
. OCE           ( 1'b1          ),
. TCE           ( 1'b0          ),
. OCLKDIV       ( serial_clk   ),
. SERCLK        ( serial_clk_5x     ),
. OCLK          ( serial_clk_5x     ),
. MIPI_CTRL     (               ),
. UPD0_SHIFT    ( 1'b0          ),
. UPD1_SHIFT    ( 1'b0          ),
. OSHIFTIN0     (               ),
. OSHIFTIN1     (               ),
. DI            ( {4'd0,paralell_data[9:8],2'd0} ),//[3:2]
. TI            (               ),
. TBYTE_IN      (               ),
. OSHIFTOUT0    ( OSHIFTIN0  ),
. OSHIFTOUT1    ( OSHIFTIN1  ),     
. DO            (               ),
. TQ            (               )
);			 
 
GTP_OUTBUFDS  GTP_OUTBUFDS_data_lane
(
   .O  ( serial_data_p ),
   .OB ( serial_data_n ),
   .I  ( tx_data_out )
);   

endmodule
