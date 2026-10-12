initial begin
 scenario(32,4,64,0,32,16,12.0,10.0,0.0,1);
 scenario(32,4,64,1,32,16,12.0,10.0,0.0,1);
 for(k=0;k<2;k=k+1) begin
  for(p=0;p<4;p=p+1) begin
   for(x=0;x<64;x=x+1) tick(0,1,(p*64+x)&255);
   if(p<3) idle(64);
  end
  idle(128);marker(16);idle(64);repeat(100) @(negedge video);
  check(si==128&&so==128&&di==128&&sd==0,"busy continuity snapshots");
 end
 check(src==384&&outn==384&&accepted==256&&published==2&&reject==0,"busy whole-frame skip retained");
 $display("EXPECTED_BUSY_SKIP source=%0d output=%0d accepted=%0d published=%0d",src,outn,accepted,published);
 $display("CANDIDATE_DONE cases=%0d errors=%0d",cases,errors);
 if(errors) $fatal(1,"extra failures");$finish;
end
endmodule
