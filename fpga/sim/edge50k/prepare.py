from pathlib import Path

here = Path(__file__).resolve().parent
source = here.parent / 'merge_rows/physical_stress/tb_merge_rows.sv'
b = source.read_bytes()
def change(old, new):
    global b
    old, new = old.encode(), new.encode()
    assert b.count(old) == 1, old
    b = b.replace(old, new)

change('href=0; data=0; repeat(2000-2*npx-((ID && MODE==10 && y%7==0)?1:0)) @(negedge clk);',
       '''href=0;
         // Distinct, nonheld HBLANK bytes: no active sample may consume these.
         for(h=0;h<2000-2*npx;h=h+1) begin
           case(h%4) 0:data=8'ha5; 1:data=8'h34; 2:data=8'h84; 3:data=8'h10; endcase
           @(negedge clk);
         end''')
change('integer capture_errors=0;', '''integer capture_errors=0;
  integer source_errors_a=0,source_errors_b=0,edge_checks_a=0,edge_checks_b=0;
  function [15:0] source_word(input integer id, row, col);
    source_word=(id?16'h8000:16'h0000) ^ ((row/480)*16'h4000) ^ ((row%480)*641+col);
  endfunction''')
change('if(ade) begin if(arows%(480+EXTRA)<480) begin qa[wa]=apix; wa=wa+1; end na=na+1; alen=alen+1; end',
       '''if(ade) begin
      if(apix!==source_word(0,arows,alen)) begin
        if(source_errors_a<8) $display("SOURCE_A row=%0d col=%0d got=%04h expected=%04h",arows,alen,apix,source_word(0,arows,alen));
        source_errors_a=source_errors_a+1;
      end
      if(alen>=638) edge_checks_a=edge_checks_a+1;
      qa[wa]=apix; wa=wa+1; na=na+1; alen=alen+1;
    end''')
change('if(bde) begin brow[blen]=bpix; nb=nb+1; blen=blen+1; end',
       '''if(bde) begin
      if(bpix!==source_word(1,brows,blen)) begin
        if(source_errors_b<8) $display("SOURCE_B row=%0d col=%0d got=%04h expected=%04h",brows,blen,bpix,source_word(1,brows,blen));
        source_errors_b=source_errors_b+1;
      end
      if(blen>=638) edge_checks_b=edge_checks_b+1;
      brow[blen]=bpix; nb=nb+1; blen=blen+1;
    end''')
change('if(frame==2 && ra==614400 && afull==0 && bfull==0 && errors==0 && capture_errors==0 &&',
       '''$display("SOURCE_CHECK A_errors=%0d B_errors=%0d A_tail_samples=%0d B_tail_samples=%0d",source_errors_a,source_errors_b,edge_checks_a,edge_checks_b);
    if(source_errors_a || source_errors_b || edge_checks_a!=1920 || edge_checks_b!=1920) $fatal(1,"Source identity failed");
    if(frame==2 && ra==614400 && afull==0 && bfull==0 && errors==0 && capture_errors==0 &&''')
change('else $display("TEST FAIL");','else $fatal(1,"Merge identity failed");')
change('((MODE==0 && PB<11.905 && reprows==0 && rb==614400) || (MODE!=0 || PB>=11.905) && reprows>0)',
       '(reprows==0 && rb==614400)')
(here / 'tb_merge_rows.sv').write_bytes(b)
print('Prepared isolated byte-preserving test; production untouched')
