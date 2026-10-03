`timescale 1ns/1ps
// Actual 50K capture + merge, with vendor clock primitives (no FIFO substitutes).
module merge_rows_camera #(parameter real PERIOD=47.619, parameter integer ID=0, EXTRA=0, VTS=705)(
 output reg clk=0, output reg cfg=1, output reg [7:0] data=0,
 output reg href=0, output reg vs=0, output reg done=0);
 always #(PERIOD/2) clk=~clk;
 integer f,y,x,h;
 reg [15:0] pix;
 function [15:0] pattern(input integer ff,yy,xx);
   pattern=(ID?16'h8000:16'h0000) ^ (ff*16'h4000) ^ (yy*641+xx);
 endfunction
 initial begin
   // Explicit falling reset edge: pixel_clk is stopped until VS enables it.
   #10; cfg=0;
   // Independent config completion, before the next VS rising edge.
   #(ID?931:613); cfg=1;
   repeat(ID?7:13) @(negedge clk);
   for(f=0;f<2;f=f+1) begin
     // HTS=2000 bytes, VTS=705 rows; 4 VS rows precede 480 active.
     vs=1; repeat(8000) @(negedge clk); vs=0;
     for(y=0;y<480+EXTRA;y=y+1) begin
       href=1;
       for(x=0;x<640;x=x+1) begin
         pix=pattern(f,y,x);
         data=pix[15:8]; @(negedge clk);
         data=pix[7:0]; @(negedge clk);
       end
       href=0; data=0; repeat(720) @(negedge clk);
     end
     repeat((VTS-484-EXTRA)*2000) @(negedge clk);
   end
   done=1;
 end
endmodule

module tb_merge_rows;
 parameter real PA=47.619, PB=47.600, PO=16.0;
 parameter integer EXTRA=0;
 parameter integer VTS=705;
 wire ac,bc,ar,br,ah,bh,av,bv,adone,bdone;
 wire [7:0] ai,bi;
 merge_rows_camera #(.PERIOD(PA),.ID(0),.EXTRA(EXTRA),.VTS(VTS)) ca(ac,ar,ai,ah,av,adone);
 merge_rows_camera #(.PERIOD(PB),.ID(1),.EXTRA(EXTRA),.VTS(VTS)) cb(bc,br,bi,bh,bv,bdone);
 reg [7:0] aid,bid; reg ahd,bhd,avd,bvd;
 always @(posedge ac) begin aid<=ai; ahd<=ah; avd<=av; end
 always @(posedge bc) begin bid<=bi; bhd<=bh; bvd<=bv; end
 wire ap,bp,ade,bde; wire [15:0] apix,bpix;
 cmos_8_16bit capture_a(ac,ar,ahd,aid,avd,ap,ade,apix);
 cmos_8_16bit capture_b(bc,br,bhd,bid,bvd,bp,bde,bpix);
 // Model device power-up GRS for capture registers without explicit RTL reset.
 // Their clock is stopped until enble, so an RTL-only simulator cannot flush Xs.
 initial begin
   #101;
   capture_a.de_out2=0; capture_a.de_out3=0; capture_a.de_o=0;
   capture_b.de_out2=0; capture_b.de_out3=0; capture_b.de_o=0;
   capture_a.pdata_out2=0; capture_a.pdata_out3=0; capture_a.pdata_o=0;
   capture_b.pdata_out2=0; capture_b.pdata_out3=0; capture_b.pdata_o=0;
 end
 reg oc=0,orn=0;
 always #(PO/2) oc=~oc;
 initial begin #200; orn=1; end
 wire [15:0] cdata; wire cde,cvs;
 cam2_merge #(.LINE_PIX(640),.LINES(480)) dut(
 .a_clk(ap),.a_rst_n(ar),.a_data(apix),.a_de(ade),.a_vs(avd),.corr_mode(4'd0),
 .b_clk(bp),.b_rst_n(br),.b_data(bpix),.b_de(bde),.b_vs(bvd),
 .o_clk(oc),.o_rst_n(orn),.c_data(cdata),.c_de(cde),.c_vs(cvs));
 reg [15:0] qa[0:620000],qb[0:620000];
 integer na=0,nb=0,ra=0,rb=0,afull=0,bfull=0;
 integer wa=0,wb=0;
 integer aeol=0,beol=0,abad=0,bbad=0;
 integer arows=0,brows=0,alen=0,blen=0;
 reg adel=0,bdel=0;
 integer capture_errors=0;
 always @(posedge ap) if(ar) begin
   if(ade) begin
     if((arows%(480+EXTRA)==0 || arows%(480+EXTRA)==479) && (alen==0 || alen==639))
       $display("CAPTURE_A frame=%0d row=%0d x=%0d data=%h",arows/(480+EXTRA),arows%(480+EXTRA),alen,apix);
     if(apix!==ca.pattern(arows/(480+EXTRA),arows%(480+EXTRA),alen)) capture_errors=capture_errors+1;
     if(arows%(480+EXTRA)<480) begin qa[wa]=apix; wa=wa+1; end
     na=na+1; alen=alen+1;
   end
   if(adel && !ade) begin
     if(alen!=640) $display("CAPTURE_A_SHORT row=%0d length=%0d",arows,alen);
     arows=arows+1; alen=0;
   end
   adel=ade;
   if(dut.u_afifo.wr_en && dut.u_afifo.full) afull=afull+1;
 end
 always @(posedge bp) if(br) begin
   if(bde) begin
     if((brows%(480+EXTRA)==0 || brows%(480+EXTRA)==479) && (blen==0 || blen==639))
       $display("CAPTURE_B frame=%0d row=%0d x=%0d data=%h",brows/(480+EXTRA),brows%(480+EXTRA),blen,bpix);
     if(bpix!==cb.pattern(brows/(480+EXTRA),brows%(480+EXTRA),blen)) capture_errors=capture_errors+1;
     if(brows%(480+EXTRA)<480) begin qb[wb]=bpix; wb=wb+1; end
     nb=nb+1; blen=blen+1;
   end
   if(bdel && !bde) begin
     if(blen!=640) $display("CAPTURE_B_SHORT row=%0d length=%0d",brows,blen);
     brows=brows+1; blen=0;
   end
   bdel=bde;
   if(dut.u_bfifo.wr_en && dut.u_bfifo.full) bfull=bfull+1;
 end
 integer frame=0,total=0,aa=0,bb=0,runlen=0,rows=0,errors=0;
 reg vd=0; reg [15:0] raw,expected;
 always @(negedge oc) if(orn) begin
   if(dut.apop && dut.afifo_rdata[16]) begin
     aeol=aeol+1; if(dut.a_fcnt!=640) begin
       abad=abad+1; if(abad<9) $display("MALFORMED_A eol=%0d pixels=%0d time=%0t",aeol,dut.a_fcnt,$time);
     end
   end
   if(dut.bpop && dut.bfifo_rdata[16]) begin
     beol=beol+1; if(dut.b_fcnt!=640) bbad=bbad+1;
   end
   if(cde) begin
     raw={cdata[4:0],cdata[10:5],cdata[15:11]};
     if(runlen<640) begin expected=qa[ra]; ra=ra+1; aa=aa+1; end
     else begin expected=qb[rb]; rb=rb+1; bb=bb+1; end
     if(raw!==expected) begin
       if(errors<8) $display("MISMATCH frame=%0d row=%0d x=%0d got=%h expect=%h rep=%b",frame,rows,runlen,raw,expected,dut.b_rep);
       errors=errors+1;
     end
     total=total+1; runlen=runlen+1;
   end else if(runlen!=0) begin
     if(runlen!=1280) errors=errors+1;
     rows=rows+1; runlen=0;
   end
   if(cvs && !vd) begin
     $display("FRAME %0d A=%0d B=%0d merged=%0d rows=%0d errors=%0d",frame,aa,bb,total,rows,errors);
     if(aa!=307200 || bb!=307200 || total!=614400 || rows!=480) errors=errors+1;
     frame=frame+1; aa=0; bb=0; total=0; rows=0;
   end
   vd=cvs;
 end
 initial begin
   wait(adone && bdone); #200000;
   $display("CAPTURE_ERRORS=%0d pendingA=%0d pendingB=%0d partialFrameA=%0d partialFrameB=%0d",capture_errors,dut.a_fcnt,dut.b_fcnt,aa,bb);
   $display("SUMMARY frames=%0d captureA=%0d/%0drows captureB=%0d/%0drows readA=%0d readB=%0d eolA=%0d eolB=%0d malformedA=%0d malformedB=%0d fullA=%0d fullB=%0d errors=%0d",frame,na,arows,nb,brows,ra,rb,aeol,beol,abad,bbad,afull,bfull,errors);
   if(frame==2 && na==(480+EXTRA)*1280 && nb==(480+EXTRA)*1280 && ra==614400 && rb==614400 && afull==0 && bfull==0 && errors==0 && capture_errors==0) $display("TEST PASS");
   else $display("TEST FAIL");
   $finish;
 end
 initial begin #150000000; $display("TIMEOUT"); $finish; end
endmodule
// Vendor GTP_IOCLKDIV uses the conventional global instance name.
module GRS_INST; reg GRSNET=0; initial #100 GRSNET=1; endmodule
