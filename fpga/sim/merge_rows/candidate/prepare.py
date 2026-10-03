from pathlib import Path
import hashlib

here = Path(__file__).resolve().parent
source = here.parents[3] / 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cam2_merge.v'
data = source.read_bytes()
(here / 'cam2_merge_reference.v').write_bytes(data)
newline = b'\r\n' if b'\r\n' in data else b'\n'
old = b'                        state  <= `UD S_COPY;'
assert data.count(old) == 1
# Replace only the state transition and add snapshot writes; retain unreachable
# S_COPY for a small reviewable patch, with no production mutation.
lines = data.splitlines(keepends=True)
for i, line in enumerate(lines):
    if old in line:
        lines[i] = newline.join([
            b'                        snap_valid <= `UD 1\'b1;',
            b'                        if (pair_cnt == LINES - 13\'d1)',
            b'                            state <= `UD S_VSYNC;',
            b'                        else begin',
            b'                            pair_cnt <= `UD pair_cnt + 13\'d1;',
            b'                            state <= `UD S_GAP_BA;',
            b'                        end', b''])
        break
needle = b"                b_rcnt <= `UD b_rcnt + 11'd1;"
assert sum(needle in line for line in lines) == 1
for i, line in enumerate(lines):
    if needle in line:
        lines[i] += newline.join([
            b'                // Snapshot only real output rows; commit validity on final pixel.',
            b'                if (!b_rep) begin',
            b'                    if (b_cur) b_memL[b_rcnt[9:0]] <= `UD b_mem1[b_rcnt[9:0]];',
            b'                    else       b_memL[b_rcnt[9:0]] <= `UD b_mem0[b_rcnt[9:0]];',
            b'                end', b''])
        break
(here / 'cam2_merge_stream_snapshot.v').write_bytes(b''.join(lines))
print('Production SHA256 (read only):', hashlib.sha256(data).hexdigest())

# Keep independent scoreboard additions local to the candidate directory.
base = (here.parent / 'tb_merge_rows.sv').read_text()
base = base.replace('EXTRA=0, VTS=705)', 'EXTRA=0, VTS=705, MODE=0)')
base = base.replace('  integer f,y,x,h;', '  integer f,y,x,h;')
base = base.replace('integer f,y,x,h;', 'integer f,y,x,h,npx;')
base = base.replace('repeat(ID?7:13)', 'if(ID && MODE==4) #20000;\n    repeat(ID?7:13)')
base = base.replace('href=1;\n       for(x=0;x<640;x=x+1)', '''npx=640;
       if(ID && MODE==1 && (y==0 || y==7 || y==479)) npx=0;
       if(ID && MODE==2 && (y==11 || y==479)) npx=320;
       if(ID && MODE==3 && (y==0 || y==7)) npx=0;
       if(ID && MODE==3 && y==11) npx=320;
       if(ID && MODE==5) npx=0;
       if(ID && MODE==6 && f==1) npx=0;
       href=(npx!=0);
       for(x=0;x<npx;x=x+1)''')
base = base.replace('repeat(720)', 'repeat(2000-2*npx)')
base = base.replace('parameter integer VTS=705;', 'parameter integer VTS=705;\n parameter integer MODE=0;')
base = base.replace('.VTS(VTS)) cb', '.VTS(VTS),.MODE(MODE)) cb')
start = base.index('  integer capture_errors=0;') if '  integer capture_errors=0;' in base else base.index(' integer capture_errors=0;')
end = base.index(' integer frame=0', start)
base = base[:start] + ''' integer capture_errors=0;
 reg [15:0] brow[0:639], lastgood[0:639];
 integer b_good_rows=0, b_bad_rows=0, b_source_row=0, j;
 reg bvs_prev=0;
 always @(posedge ap) if(ar) begin
   if(ade) begin qa[wa]=apix; wa=wa+1; na=na+1; alen=alen+1; end
   if(adel && !ade) begin
     if(alen!=640) capture_errors=capture_errors+1;
     arows=arows+1; alen=0;
   end
   adel=ade;
   if(dut.u_afifo.wr_en && dut.u_afifo.full) afull=afull+1;
 end
 always @(posedge bp) if(br) begin
   if(bvd && !bvs_prev) b_source_row=0;
   bvs_prev=bvd;
   if(bde) begin brow[blen]=bpix; nb=nb+1; blen=blen+1; end
   if(bdel && !bde) begin
     if(blen==640 && b_source_row<480) begin
       for(j=0;j<640;j=j+1) begin qb[wb]=brow[j]; wb=wb+1; end
       b_good_rows=b_good_rows+1;
     end else if(blen!=640) b_bad_rows=b_bad_rows+1;
     b_source_row=b_source_row+1;
     brows=brows+1; blen=0;
   end
   bdel=bde;
   if(dut.u_bfifo.wr_en && dut.u_bfifo.full) bfull=bfull+1;
 end
 integer realrows=0,reprows=0,blackrows=0,real_to_rep=0,rep_to_real=0;
 integer astall=0,bstall=0,snapchecks=0;
 reg rowrep=0,previousrep=0,havegood=0;
''' + base[end:]
base = base.replace('if(dut.apop &&', '''if(!dut.afifo_empty && !dut.apop) astall=astall+1;
   if(!dut.bfifo_empty && !dut.bpop) bstall=bstall+1;
   if(dut.apop &&''')
base = base.replace(' integer frame=0', ''' integer cycle=0, pair_start=-1, min_pair_service=1000000, service;
 always @(posedge oc) if(orn) begin
   cycle=cycle+1;
   if(dut.state==1 && dut.a_rcnt==0) pair_start=cycle;
   if(dut.state==0 && pair_start>=0) begin
     service=cycle-pair_start+1;
     if(service<min_pair_service) min_pair_service=service;
     pair_start=-1;
   end
 end
 integer frame=0''')
base = base.replace('$display("SNAPSHOT real=', '$display("MIN_PAIR_SERVICE_CLOCKS=%0d",min_pair_service);\n   $display("SNAPSHOT real=')
base = base.replace('if(runlen<640) begin expected=qa[ra]; ra=ra+1; aa=aa+1; end\n     else begin expected=qb[rb]; rb=rb+1; bb=bb+1; end', '''if(runlen<640) begin
       expected=qa[ra]; ra=ra+1; aa=aa+1;
     end else begin
       if(runlen==640) begin
         rowrep=dut.b_rep;
         if(rowrep) begin
           reprows=reprows+1;
           if(!havegood) blackrows=blackrows+1;
           if(!previousrep && realrows>0) real_to_rep=real_to_rep+1;
         end else begin
           realrows=realrows+1;
           if(previousrep) rep_to_real=rep_to_real+1;
         end
         previousrep=rowrep;
       end
       if(rowrep) expected=havegood?lastgood[runlen-640]:16'h0000;
       else begin expected=qb[rb]; rb=rb+1; end
       bb=bb+1;
     end''')
base = base.replace('total=total+1; runlen=runlen+1;', '''if(runlen>=640 && !rowrep) lastgood[runlen-640]=raw;
     if(runlen==1279 && !rowrep) havegood=1;
     total=total+1; runlen=runlen+1;''')
base = base.replace('rows=rows+1; runlen=0;', '''if(havegood) begin
       for(j=0;j<640;j=j+1) begin
         raw={dut.b_memL[j][4:0],dut.b_memL[j][10:5],dut.b_memL[j][15:11]};
         if(raw!==lastgood[j]) errors=errors+1;
       end
       snapchecks=snapchecks+1;
     end
     rows=rows+1; runlen=0;''')
base = base.replace('if(frame==2 && na==(480+EXTRA)*1280 && nb==(480+EXTRA)*1280 && ra==614400 && rb==614400 && afull==0 && bfull==0 && errors==0 && capture_errors==0)', '''$display("SNAPSHOT real=%0d repeat=%0d black=%0d realToRep=%0d repToReal=%0d checks=%0d captureGoodB=%0d captureBadB=%0d astall=%0d bstall=%0d",realrows,reprows,blackrows,real_to_rep,rep_to_real,snapchecks,b_good_rows,b_bad_rows,astall,bstall);
   if(frame==2 && ra==614400 && afull==0 && bfull==0 && errors==0 && capture_errors==0 &&
      ((MODE==0 && PB<11.905 && reprows==0 && rb==614400) || (MODE!=0 || PB>=11.905) && reprows>0))''')
# A queue must exclude the cap row when EXTRA=1.
base = base.replace('$display("SNAPSHOT real=', '$display("MIN_PAIR_SERVICE_CLOCKS=%0d",min_pair_service);\n   $display("SNAPSHOT real=')
base = base.replace('qa[wa]=apix; wa=wa+1;', 'if(arows%(480+EXTRA)<480) begin qa[wa]=apix; wa=wa+1; end')
(here / 'tb_merge_rows.sv').write_text(base)
