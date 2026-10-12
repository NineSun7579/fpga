`timescale 1ns/1ps
module tb_cmos50k;
  reg pclk=0;
  always #5 pclk=~pclk;
  reg rst_n=0, raw_vs=0, raw_href=0;
  reg [7:0] raw_data=0;
  reg vs_d0=0, href_d0=0;
  reg [7:0] data_d0=0;
  always @(posedge pclk) begin
    vs_d0<=raw_vs; href_d0<=raw_href; data_d0<=raw_data;
  end
  wire pixel_clk, de;
  wire [15:0] data_out;
  cmos_8_16bit dut(.pclk(pclk),.rst_n(rst_n),.de_i(href_d0),
    .pdata_i(data_d0),.vs_i(vs_d0),.pixel_clk(pixel_clk),
    .de_o(de),.pdata_o(data_out));
  GTP_GRS GRS_INST(.GRS_N(rst_n));

  reg [15:0] expected [0:400000];
  integer expected_n, got_n, bad_data, rows, row_n;
  integer rows639, rows640, rows641, rows_other, vs_overlap;
  integer first_bad, case_id=0, failures=0;
  integer local_bad, bad_rows, row_bad, diagnostic_rows;
  integer row_expected [0:479];
  reg [15:0] last_word;
  reg collecting=0, old_de=0;
  real raw_end, de_end, vs_rise;
  integer pixel_edges;
  integer consumer_vs_overlap;
  always @(posedge pixel_clk) begin
    // A real downstream synchronous consumer sees the old output registers.
    if(collecting && de===1'b1 && vs_d0===1'b1)
      consumer_vs_overlap=consumer_vs_overlap+1;
    #1;
    if (collecting) begin
      pixel_edges=pixel_edges+1;
      if (de===1'b1) begin
        if(rows>=480 || row_n>=row_expected[rows] || data_out !== word_for(rows,row_n)) begin
          local_bad=local_bad+1; row_bad=row_bad+1;
          if(diagnostic_rows<3 && row_bad==1) begin
            $display("ROW_BAD case=%0d row=%0d col=%0d row_expected=%0d expected_word=%04h actual=%04h previous=%04h",case_id,rows,row_n,row_expected[rows],word_for(rows,row_n),data_out,last_word);
            diagnostic_rows=diagnostic_rows+1;
          end
        end
        last_word=data_out;
        if (data_out !== expected[got_n] || got_n>=expected_n) begin
          bad_data=bad_data+1;
          if (first_bad<0) begin
            first_bad=got_n;
            $display("FIRST_BAD case=%0d index=%0d expected=%04h actual=%04h time=%0t",case_id,got_n,expected[got_n],data_out,$time);
          end
        end
        got_n=got_n+1; row_n=row_n+1;
        if(vs_d0) vs_overlap=vs_overlap+1;
      end
      if(old_de && !de) begin
        if(row_bad>0 || row_n!=row_expected[rows]) bad_rows=bad_rows+1;
        rows=rows+1;
        case(row_n)
          639: rows639=rows639+1;
          640: rows640=rows640+1;
          641: rows641=rows641+1;
          default: rows_other=rows_other+1;
        endcase
        row_n=0; row_bad=0; de_end=$realtime;
      end
      old_de=de;
    end
  end

  function [15:0] word_for(input integer row, input integer col);
    word_for=(row*641+col+16'h1357)&16'hffff;
  endfunction

  // First HREF rises off-edge; subsequent bytes change on falling PCLK.
  // parity changes by one whole PCLK while subphase sweeps setup time.
  task run_case(input integer phase_ns, input integer gap,
    input integer odd_width, input integer odd_stride,
    input integer nrows, input integer tail_gap, input integer check_clean);
    integer r,b,w,k,exp_rows;
    reg [15:0] value;
    begin
      collecting=0; rst_n=0; raw_vs=0; raw_href=0; raw_data=0;
      repeat(12) @(negedge pclk);
      rst_n=1;
      repeat(4) @(negedge pclk);
      raw_vs=1;
      repeat(8) @(negedge pclk);
      raw_vs=0;
      repeat(16) @(negedge pclk);
      case_id=case_id+1;
      expected_n=0;
      for(r=0;r<nrows;r=r+1) begin
        w=1280;
        if((odd_stride>0 && r%odd_stride==0) || (odd_stride==-1 && r==nrows-1)) w=odd_width;
        row_expected[r]=w/2;
        for(k=0;k<w/2;k=k+1) begin
          expected[expected_n]=word_for(r,k);
          expected_n=expected_n+1;
        end
      end
      got_n=0;bad_data=0;rows=0;row_n=0;rows639=0;rows640=0;
      rows641=0;rows_other=0;vs_overlap=0;first_bad=-1;old_de=0;
      local_bad=0;bad_rows=0;row_bad=0;diagnostic_rows=0;last_word=0;
      pixel_edges=0; consumer_vs_overlap=0; collecting=1;
      #(phase_ns);
      for(r=0;r<nrows;r=r+1) begin
        w=1280;
        if((odd_stride>0 && r%odd_stride==0) || (odd_stride==-1 && r==nrows-1)) w=odd_width;
        raw_href=1;
        for(b=0;b<w;b=b+1) begin
          value=word_for(r,b/2);
          raw_data=(b%2==0)?value[15:8]:value[7:0];
          @(posedge pclk);
          @(negedge pclk);
        end
        raw_href=0; raw_end=$realtime;
        if(r<nrows-1) repeat(gap) @(negedge pclk);
      end
      repeat(tail_gap) @(negedge pclk);
      raw_vs=1; vs_rise=$realtime;
      repeat(24) @(negedge pclk);
      collecting=0;
      $display("RESULT case=%0d phase_ns=%0d gap=%0d width=%0d stride=%0d input_rows=%0d tail=%0d expected=%0d got=%0d rows=%0d r639=%0d r640=%0d r641=%0d other=%0d bad_data=%0d vs_overlap=%0d tail_latency_ns=%0.0f vs_after_raw_end_ns=%0.0f pixel_edges=%0d",case_id,phase_ns,gap,odd_width,odd_stride,nrows,tail_gap,expected_n,got_n,rows,rows639,rows640,rows641,rows_other,bad_data,vs_overlap,de_end-raw_end,vs_rise-raw_end,pixel_edges);
      $display("ROW_SCORE case=%0d local_bad_samples=%0d bad_rows=%0d consumer_vs_overlap=%0d",case_id,local_bad,bad_rows,consumer_vs_overlap);
      if(check_clean && (got_n!=expected_n || rows!=nrows || bad_data!=0 || vs_overlap!=0)) begin
        failures=failures+1;
        $display("CLEAN_FAIL case=%0d",case_id);
      end
      if(odd_stride>0 && (rows!=nrows || got_n<expected_n || local_bad!=got_n-expected_n || bad_rows!=local_bad)) begin
        failures=failures+1;
        $display("ODD_SIGNATURE_FAIL case=%0d",case_id);
      end
      if(tail_gap<5 && consumer_vs_overlap==0) begin
        failures=failures+1;
        $display("VS_SIGNATURE_FAIL case=%0d",case_id);
      end
    end
  endtask

  integer p;
  initial begin
    // Both /2 parities and four asynchronous first-HREF setup offsets.
    for(p=1;p<=19;p=p+6) run_case(p,720,1280,0,480,100,1);
    run_case(1,721,1280,0,480,100,1);
    run_case(11,721,1280,0,480,100,1);
    // Short or extra byte on 1/17 rows, with both starting parities.
    run_case(1,720,1279,17,480,100,0);
    run_case(11,720,1279,17,480,100,0);
    run_case(1,720,1281,17,480,100,0);
    run_case(11,720,1281,17,480,100,0);
    // Boundary proximity: raw VSYNC is not delayed with packed DE/data.
    run_case(1,720,1280,0,480,0,0);
    run_case(11,720,1280,0,480,1,0);
    run_case(1,720,1280,0,480,2,0);
    run_case(11,720,1280,0,480,4,0);
    run_case(1,720,1280,0,480,8,1);
    // A whole missing source line reproduces the stable observed total.
    run_case(1,720,1280,0,479,100,1);
    // 479 source rows plus a last row shorter by 280 / 88 bytes.
    run_case(1,720,1000,-1,479,100,1);
    run_case(11,720,1192,-1,479,100,1);
    $display("SUMMARY clean_failures=%0d",failures);
    if(failures) $fatal(1,"Clean frames failed");
    $finish;
  end
endmodule
