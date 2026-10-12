// Measure sampled CDC-before-FIR high duration, same location as board counter.
integer high_cycles=0,high_first=0,high_last=0,falls=0;
reg width_prev=0;
always @(posedge video) begin
 if(rst) begin high_cycles=0;high_first=0;high_last=0;falls=0;width_prev=0;end
 else begin
  if(sv) high_cycles++;
  if(!sv&&width_prev) begin
   high_last=high_cycles;
   if(falls==0) high_first=high_cycles;
   falls++;high_cycles=0;
  end
  width_prev=sv;
 end
end
task check_long_level(input integer min_last);
 check(falls==2,"two complete long VSYNC levels");
 check(high_first>=5924&&high_first<=5926,"initial long VSYNC width");
 check(high_last>=min_last&&high_last<=5926,"closing long VSYNC retained");
 $display("LONG_LEVEL case=%0d first=%0d last=%0d falls=%0d",cases,high_first,high_last,falls);
endtask
initial begin
 // 7900 PCLK * 12ns / 16ns = 5925 video cycles. Tail is independent.
 scenario(640,480,616,2000,32,7900,12.0,16.0,0.0,1);
 check_long_level(5924);
 scenario(640,480,616,1,32,7900,12.0,16.0,0.0,IS_CANDIDATE);
 if(IS_CANDIDATE) check(accepted==307200&&published==1&&reject==0,"long pulse short tail candidate");
 else check(accepted==307199&&published==0&&reject[15:0]==1,"long pulse short tail baseline");
 check_long_level(5920);
 // Large final-line backlog can shorten replayed high level; still thousands
 // of cycles, never a one-cycle SOF replacement. 14813*12/30 = 5925.2.
 scenario(640,480,616,1,32,14813,12.0,30.0,2.1,IS_CANDIDATE);
 if(IS_CANDIDATE) check(accepted==307200&&published==1&&reject==0,"long pulse backlog candidate");
 else check(accepted<307200&&published==0&&reject[15:0]==1,"long pulse backlog baseline");
 check_long_level(5700);
 $display("CANDIDATE_DONE cases=%0d errors=%0d",cases,errors);
 if(errors) $fatal(1,"long VSYNC failures");$finish;
end
endmodule
