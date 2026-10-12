initial begin
 scenario(640,480,616,1,32,16,12.0,16.0,0.0,IS_CANDIDATE);
 if(IS_CANDIDATE) check(accepted==307200&&published==1&&reject==0,"candidate full-size repair");
 else check(accepted==307199&&published==0&&reject[15:0]==1,"baseline full-size failure");
 scenario(640,480,616,2000,616,64,11.905,10.0,0.1,1);
 scenario(640,480,616,2000,616,64,12.0,30.0,2.1,1);
 scenario(640,480,616,1,32,16,12.0,30.0,2.1,IS_CANDIDATE);
 // Narrow pulses across clock ratios and phases, no artificial head blank.
 periods[0]=5;periods[1]=10;periods[2]=16;
 periods[3]=23;periods[4]=24;periods[5]=30;
 for(f=0;f<6;f=f+1) for(p=0;p<4;p=p+1)
  scenario(32,4,64,128,0,1,12.0,periods[f],p*2.1,IS_CANDIDATE);
 scenario(640,480,616,2000,616,64,12.0,16.0,0.0,1);
 for(k=0;k<2;k=k+1) begin
  for(p=0;p<480;p=p+1) begin
   for(x=0;x<1280;x=x+1) tick(0,1,(p*1280+x)&255);
   if(p<479) idle(616);
  end
  idle(2000);marker(64);idle(616);repeat(100) @(negedge video);
  check(si==307200&&so==307200&&di==307200&&sd==0,"continuous VGA snapshots");
 end
 check(src==921600&&outn==921600&&accepted==921600&&published==3&&reject==0,"continuous VGA publication");
 $display("CONTINUOUS frames=3 source=%0d output=%0d accepted=%0d published=%0d",src,outn,accepted,published);
 $display("CANDIDATE_DONE cases=%0d errors=%0d",cases,errors);
 if(errors) $fatal(1,"candidate failures");
 $finish;
end
endmodule
