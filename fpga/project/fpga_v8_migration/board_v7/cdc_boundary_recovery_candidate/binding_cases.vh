integer saved_out,saved_publish;
initial begin
 // Actual capture + negedge stage, distinct cam/video requests, real FIR,
 // real DDR writer/controller. This endpoint models normal completion only.
 scenario(32,4,64,128,32,16,11.905,7.619,0.1,1);
 saved_out=outn;saved_publish=published;
 #1;video_request=1;#0.2;video_request=0;
 repeat(200) @(negedge video);
 check(boundary_fault && abort_req && outn==saved_out && published==saved_publish,"binding video reset no replay");
 $display("RECOVERY_BINDING video_reset before=%0d after=%0d fault=%b",saved_out,outn,boundary_fault);
 // Explicit system reset followed by first complete VGA frame: strict 307200.
 scenario(640,480,616,2000,616,64,11.905,7.619,0.1,1);
 saved_out=outn;saved_publish=published;
 #1;cam_request=1;#0.2;cam_request=0;
 // New real capture input while sticky fault must remain quarantined.
 for(x=0;x<128;x=x+1) tick(0,1,x);
 idle(128);marker(16);idle(64);
 repeat(200) @(negedge video);
 check(boundary_fault && abort_req && outn==saved_out && published==saved_publish,"binding source reset blocks new input");
 $display("RECOVERY_BINDING source_reset output=%0d publish=%0d fault=%b",outn,published,boundary_fault);
 scenario(640,480,616,2000,616,64,11.905,7.619,0.1,1);
 // Inject actual pixel resource full while a real capture token is pending.
 // Resource forcing is explicit fault injection, not a FIFO replacement.
 force chain.ov5640_cdc.pixel_full=1'b1;
 for(x=0;x<64;x=x+1) tick(0,1,x);
 idle(32);release chain.ov5640_cdc.pixel_full;
 repeat(100) @(negedge video);
 check(boundary_fault && abort_req,"binding full routed to DDR abort");
 saved_out=outn;saved_publish=published;
 marker(16);idle(64);
 check(outn==saved_out && published==saved_publish,"full forbids local rearm");
 scenario(640,480,616,2000,616,64,11.905,7.619,0.1,1);
 $display("RECOVERY_BINDING full_global_reset source=%0d output=%0d admitted=%0d published=%0d",src,outn,accepted,published);
 $display("BINDING_DONE errors=%0d",errors);
 if(errors) $fatal(1,"binding recovery failures");$finish;
end
endmodule
