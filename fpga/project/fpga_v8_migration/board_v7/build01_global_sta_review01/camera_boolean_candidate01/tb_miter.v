`timescale 1ns/1ps
module ov5640_cdc_fifo(input wr_clk,wr_rst,wr_en,input [23:0] wr_data,
 output wr_full,input rd_clk,rd_en,output [23:0] rd_data,output rd_empty,
 input rd_rst,output almost_full,almost_empty);
 assign wr_full=tb_miter.full;
 assign rd_empty=tb_miter.empty;
 assign rd_data=24'h123456;
 assign almost_full=wr_full;assign almost_empty=rd_empty;
endmodule
module tb_miter;
 reg clk=0,hclk=0;always #5 clk=~clk;always #7 hclk=~hclk;
 reg rst=1,hrst=1,rawvs=0,href=0,byteok=0,vs=0,valid=0;
 reg read=0,acquire=0,release_s=0;reg [4:0] word=0;
 reg full=0,empty=1;reg [23:0] data=0;
 wire [37:0] go,co;
 golden_sfd g(clk,rst,hclk,hrst,rawvs,href,byteok,vs,valid,
 read,acquire,release_s,word,go[31:0],go[32],go[33],go[34],go[35],go[36]);
 candidate_sfd c(clk,rst,hclk,hrst,rawvs,href,byteok,vs,valid,
 read,acquire,release_s,word,co[31:0],co[32],co[33],co[34],co[35],co[36]);
 wire [154:0] gc,cc;
 golden_cdc gd(gc[31:0],gc[63:32],gc[95:64],gc[127:96],clk,rst,
 data,valid,href,vs,hclk,hrst,gc[151:128],gc[152],gc[153],gc[154]);
 candidate_cdc cd(cc[31:0],cc[63:32],cc[95:64],cc[127:96],clk,rst,
 data,valid,href,vs,hclk,hrst,cc[151:128],cc[152],cc[153],cc[154]);
 reg crst=1,clear=0,seed=0,inc=0;
 wire [15:0] qg,qc,ng,nc;
 golden_sfd_counter #(.W(16)) kg(clk,crst,clear,seed,inc,qg,ng);
 candidate_sfd_counter #(.W(16)) kc(clk,crst,clear,seed,inc,qc,nc);
 reg [31:0] rng=32'h643219ab;
 function [31:0] random_next(input [31:0] x);
 reg [31:0] y;begin y=x^(x<<13);y=y^(y>>17);random_next=y^(y<<5);end endfunction
 integer checks=0,cycles=0,n,k;reg [15:0] expected;
 task compare;
 begin
   if(go[36:0]!==co[36:0] || gc!==cc ||
      g.mailbox!==c.mailbox || g.host_bank!==c.host_bank ||
      {g.gap_q,g.bytes_q,g.aligned_q,g.native_q,g.seq_q,g.odd_q,g.segments_q,g.overlap_q,g.raw_overlap_q} !==
      {c.gap_q,c.bytes_q,c.aligned_q,c.native_q,c.seq_q,c.odd_q,c.segments_q,c.overlap_q,c.raw_overlap_q} ||
      {gd.src_count,gd.src_drop,gd.src_snapshot,gd.count_prefix,gd.drop_prefix} !==
      {cd.src_count,cd.src_drop,cd.src_snapshot,cd.count_prefix,cd.drop_prefix}) begin
      $display("FAIL full miter cycle=%0d",cycles);$fatal(1);
   end
   checks=checks+1;
 end endtask
 // Independent video/host-clock observation includes bus result retention.
 always @(posedge hclk) begin #1;if(cycles>3)compare;end
 initial begin
   repeat(4)@(negedge clk);rst=0;hrst=0;crst=0;
   // Exhaustive one-step truth table over every 16-bit state and all controls.
   for(n=0;n<65536;n=n+1)begin
     for(k=0;k<8;k=k+1)begin
       @(negedge clk);clear=k[2];seed=k[1];inc=k[0];
       kg.q=n;kc.q=n;
       kg.prefix={(&kg.q[11:0]),(&kg.q[7:0]),(&kg.q[3:0])};
       kc.prefix=kg.prefix;
       expected=clear?{15'b0,seed}:(n+inc);
       #1;if(ng!==nc || ng!==(16'(n+inc)))$fatal(1,"next_q mismatch");
       @(posedge clk);#1;
       if(qg!==qc || qc!==expected || kg.prefix!==kc.prefix ||
          kc.prefix!=={(&qc[11:0]),(&qc[7:0]),(&qc[3:0])})$fatal(1,"counter mismatch");
     end
   end
   $display("PASS exhaustive counter 524288 state/control transitions");
   for(cycles=0;cycles<50000;cycles=cycles+1)begin
     @(negedge clk);rng=random_next(rng);
     {rawvs,href,byteok,vs,valid,read,acquire,release_s,word,full,empty}=rng[14:0];
     data=rng[23:0];
     rst=(cycles%997)==0;hrst=(cycles%1237)==0;
     // Directed large-value deposits cover prefix rollover beyond short traces.
     if(cycles%503==20)begin
       g.cg.q=16'hfffe;c.cg.q=16'hfffe;
       g.cg.prefix=3'b111;c.cg.prefix=3'b111;
       gd.src_count=32'hfffffffe;cd.src_count=32'hfffffffe;
       gd.src_drop=32'hfffffffe;cd.src_drop=32'hfffffffe;
       gd.count_prefix=7'b0;cd.count_prefix=7'b0;
       gd.drop_prefix=7'b0;cd.drop_prefix=7'b0;
       // FFFE is not all ones at any >=4-bit boundary.
       g.cg.prefix=0;c.cg.prefix=0;
       valid=1;full=1;vs=0;g.vs_q=0;c.vs_q=0;gd.src_vs_q=0;cd.src_vs_q=0;
     end
     if(cycles%503==21)begin valid=1;full=1;vs=0;end
     @(posedge clk);#1;compare;
   end
   $display("PASS actual RTL miter camera_cycles=%0d observations=%0d seed=643219ab",cycles,checks);
   $finish;
 end
endmodule
