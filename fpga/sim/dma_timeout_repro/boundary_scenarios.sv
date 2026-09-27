 integer case_id=0, failures=0, published=0, dropped=0;
 integer kind,phase,gap,extra, seed_new, old_last=0;
 integer accept_n=0, first_pixel=-1, sof_cycle=-1, admit_cycle=-1;
 reg trace_on=0;
 always @(posedge clk) if(!rst && trace_on) begin
   if(camera.raw_sof) begin
     sof_cycle=cycle;
     $display("TRACE case=%0d SOF cycle=%0d flush=%0d count=%0d complete=%b busy=%b",case_id,cycle,camera.flush_count,camera.pixel_count,camera.capture_complete,camera.engine_busy);
   end
   if(camera.m_vsync) begin
     admit_cycle=cycle;accept_n=0;first_pixel=-1;
     $display("TRACE case=%0d ADMIT cycle=%0d flush=%0d",case_id,cycle,camera.flush_count);
   end
   if(camera.m_data_valid) begin
     if(accept_n==0)begin first_pixel=pixel;$display("TRACE case=%0d FIRST cycle=%0d pixel=%h",case_id,cycle,pixel);end
     accept_n=accept_n+1;
   end
   if(done) $display("TRACE case=%0d DONE cycle=%0d tag=%b count=%0d good=%b",case_id,cycle,cur_tag,camera.pixel_count,camera.frame_good);
 end
 task automatic fresh;
 begin
   trace_on=0;sv=0;pv=0;ack=0;
   idle();rst=1;repeat(6)@(negedge clk);rst=0;idle();
   case_id=case_id+1;accept_n=0;first_pixel=-1;sof_cycle=-1;admit_cycle=-1;
   for(integer z=0;z<196608;z=z+1)mem[z]=8'hcc;
   trace_on=1;
 end endtask
 task automatic pulse_and_pixels(input integer blank,input integer count);
 begin
   sv=1;
   if(blank==0) begin
     pixel=seed_new;pv=1;@(negedge clk);sv=0;
     for(integer z=1;z<count;z=z+1)begin pixel=seed_new+z;@(negedge clk);end
     pv=0;
   end else begin
     @(negedge clk);sv=0;
     repeat(blank-1)@(negedge clk);
     pixels(seed_new,count);
   end
 end endtask
 task automatic verify_bank(input integer bank,input integer seed,input integer seq);
 integer mismatches;reg [15:0] actual;
 begin
   mismatches=0;
   for(integer z=0;z<PIXELS;z=z+1)begin
     actual={mem[bank+z*2+1],mem[bank+z*2]};
     if(actual!==16'(seed+z))begin
       if(mismatches==0)$display("BAD_PUBLISHED case=%0d kind=%0d phase=%0d gap=%0d extra=%0d seq=%0d index=%0d actual=%h expected=%h sof=%0d admit=%0d first=%h",case_id,kind,phase,gap,extra,seq,z,actual,16'(seed+z),sof_cycle,admit_cycle,16'(first_pixel));
       mismatches=mismatches+1;
     end
   end
   if(mismatches!=0)failures=failures+1;
   if({mem[bank+WORDS*16+3],mem[bank+WORDS*16+2],mem[bank+WORDS*16+1],mem[bank+WORDS*16]}!==seq)$fatal(1,"tag mismatch");
   $display("VERIFY case=%0d seq=%0d mismatch=%0d pixels=%0d",case_id,seq,mismatches,PIXELS);
 end endtask
 task automatic settle;
 begin
   repeat(1200)@(negedge clk);idle();
   if(kind==0)begin
     if(last_cnt==1)begin verify_bank(BANK0,seed_new,1);published=published+1;end
     else if(last_cnt==0)dropped=dropped+1;
     else $fatal(1,"unexpected flush publication count");
   end else begin
     if(last_cnt>=1)verify_bank(BANK0,'h1000,1);
     if(last_cnt==2)begin verify_bank(BANK1,seed_new,2);published=published+1;end
     else dropped=dropped+1;
     if(last_cnt>2)$fatal(1,"unexpected boundary publication count");
   end
   $display("RESULT case=%0d kind=%0d phase=%0d gap=%0d extra=%0d last=%0d accepted=%0d first=%h",case_id,kind,phase,gap,extra,last_cnt,accept_n,16'(first_pixel));
   if(aw_count!=b_count||bus_active||left!=0)$fatal(1,"boundary AXI ledger mismatch");
 end endtask
 initial begin
   for(j=0;j<196608;j=j+1)mem[j]=8'hcc;
   repeat(6)@(negedge clk);rst=0;idle();
   kind=0;
   for(extra=0;extra<=8;extra=extra+8)
   for(phase=0;phase<=6;phase=phase+1)
   for(gap=0;gap<=8;gap=gap+1)begin
     fresh();seed_new='h4000;
     send_frame('h2000,13);
     wait(camera.flush_count==4);@(negedge clk);
     repeat(phase)@(negedge clk);
     $display("CASE %0d FLUSH phase=%0d gap=%0d extra=%0d",case_id,phase,gap,extra);
     pulse_and_pixels(gap,PIXELS+extra);settle();
   end
   extra=0;gap=8;
   for(kind=1;kind<=3;kind=kind+1)
   for(phase=0;phase<=8;phase=phase+1)begin
     fresh();seed_new='h6000;
     $display("CASE %0d BOUNDARY kind=%0d phase=%0d gap=%0d",case_id,kind,phase,gap);
     if(kind==1)begin
       sof();
       fork
         pixels('h1000,PIXELS);
         begin repeat(PIXELS-4+phase)@(negedge clk);pulse_and_pixels(gap,PIXELS);end
       join
     end else begin
       send_frame('h1000,PIXELS);
       if(kind==2)wait(wv&&wr&&wl&&!cur_tag&&(offset==BANK0+WORDS*16-16));
       else wait(wv&&wr&&wl&&cur_tag);
       @(negedge clk);repeat(phase)@(negedge clk);
       pulse_and_pixels(gap,PIXELS);
     end
     settle();
   end
   $display("BOUNDARY SUMMARY cases=%0d published_new=%0d dropped_new=%0d bad_published=%0d FIFO_WORDS=%0d",case_id,published,dropped,failures,WORDS);
   $finish;
 end
 initial begin #100000000;$fatal(1,"boundary timeout case=%0d kind=%0d phase=%0d gap=%0d state=%0d",case_id,kind,phase,gap,state);end
endmodule
