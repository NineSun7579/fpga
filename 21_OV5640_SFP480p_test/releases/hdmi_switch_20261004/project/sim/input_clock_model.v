`timescale 1ns/1ps
module GTP_CLKBUFG(input CLKIN,output CLKOUT);
    assign CLKOUT=CLKIN;
endmodule
// Fast 1:1 external-feedback PLL model for long pixel tests. The actual
// vendor model independently verifies the configured phase and lock/reset.
// Follow source edges so unplug stops this clock and rate changes reacquire.
module GTP_PLL_E3 #(
    parameter real CLKIN_FREQ=148.5,
    parameter STATIC_RATIOI=1,STATIC_RATIOM=1,STATIC_RATIOF=8,
    parameter STATIC_RATIO0=8,STATIC_RATIO1=8,
    parameter STATIC_DUTY0=8,STATIC_DUTY1=8,
    parameter STATIC_PHASE0=3,STATIC_PHASE1=0,
    parameter STATIC_CPHASE0=5,STATIC_CPHASE1=0,
    parameter INTERNAL_FB="DISABLE",EXTERNAL_FB="CLKOUT1",BANDWIDTH="HIGH"
)(
    input CLKIN1,CLKIN2,CLKIN_SEL,CLKIN_SEL_EN,CLKFB,PLL_PWD,RST,RSTODIV,
    input PFDEN,ICP_BASE,CRIPPLE_SEL,PHASE_DIR,PHASE_STEP_N,LOAD_PHASE,
    input [3:0] ICP_SEL,input [2:0] LPFRES_SEL,PHASE_SEL,
    input [9:0] RATIOI,RATIOF,RATIO0,RATIO1,RATIO2,RATIO3,RATIO4,
    input [6:0] RATIOM,input [9:0] DUTY0,DUTY1,DUTY2,DUTY3,DUTY4,
    input CLKOUT0_SYN,CLKOUT0_EXT_SYN,CLKOUT1_SYN,CLKOUT2_SYN,
    input CLKOUT3_SYN,CLKOUT4_SYN,CLKOUT5_SYN,
    output reg CLKOUT0=0,output CLKOUT1,output reg LOCK=0
);
    realtime last_rise=0;
    real source_period=1000.0/CLKIN_FREQ, previous_period=0;
    real phase_fraction=(STATIC_CPHASE0+STATIC_PHASE0/8.0)/STATIC_RATIO0;
    integer stable_edges=0;
    assign CLKOUT1=CLKIN1;
    always @(posedge CLKIN1 or posedge RST) begin
        if(RST) begin LOCK<=0; stable_edges=0; last_rise=0; end
        else begin
            if(last_rise>0) source_period=$realtime-last_rise;
            last_rise=$realtime;
            if(previous_period>0 &&
              (source_period<previous_period*0.99 || source_period>previous_period*1.01)) begin
                stable_edges=0; LOCK<=0;
            end else begin
                stable_edges=stable_edges+1;
                if(stable_edges>=16) LOCK<=1;
            end
            previous_period=source_period;
        end
    end
    always @(CLKIN1) CLKOUT0 <= #(source_period*phase_fraction) CLKIN1;
endmodule
module GTP_CLKBUFR(input CLKIN,output CLKOUT);
    assign CLKOUT=CLKIN;
endmodule
`ifndef TOP_BOOT_CLOCK_MOCKS
module GTP_IOCLKBUF #(parameter GATE_EN="FALSE")
    (input CLKIN,DI,output CLKOUT);
    assign CLKOUT=CLKIN;
endmodule
`endif
// Falling sample and following rising retime, matching Logos GTP_IDDR_E2 Q1.
module GTP_IDDR_E2 #(parameter GRS_EN="FALSE")
    (input D,RS,CLK,output reg Q0=0,Q1=0);
    reg fall_q=0,rise_q=0;
    always @(negedge CLK or posedge RS) if(RS) fall_q<=0; else fall_q<=D;
    always @(posedge CLK or posedge RS)
        if(RS) begin Q1<=0; rise_q<=0; Q0<=0; end
        else begin Q1<=fall_q; rise_q<=D; Q0<=rise_q; end
endmodule
