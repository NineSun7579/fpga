`timescale 1ns/1ps
module tb_fourstate;
function automatic reg state4(input integer n);
    case(n) 0:state4=0; 1:state4=1; 2:state4=1'bx; 3:state4=1'bz; endcase
endfunction
reg trans, a, req, b, resp, bt, aw, rst, waiting, changed, valid, ready, active;
reg old_abort, new_abort, old_clear, new_clear, wp;
integer i,j,k, abort_vectors=0, clear_vectors=0;
initial begin
    for(i=0;i<16384;i=i+1) begin
        trans=state4(i%4); a=state4((i/4)%4); req=state4((i/16)%4);
        b=state4((i/64)%4); resp=state4((i/256)%4);
        bt=state4((i/1024)%4); aw=state4((i/4096)%4);
        old_abort=trans && (a || req || (b && resp)) && (b || (a && !bt && !aw));
        new_abort=trans && ((b && (a || req || resp)) || (a && !bt && !aw));
        if(old_abort !== new_abort) $fatal(1,"abort fourstate mismatch vector=%0d",i);
        abort_vectors=abort_vectors+1;
    end
    for(i=0;i<65536;i=i+1) begin
        rst=state4(i%4); a=state4((i/4)%4); waiting=state4((i/16)%4);
        changed=state4((i/64)%4); bt=state4((i/256)%4);
        valid=state4((i/1024)%4); ready=state4((i/4096)%4); active=state4((i/16384)%4);
        wp=((a ? active : (valid && active)) == 1'b1) && (ready == 1'b1);
        old_clear=rst || a || (waiting ? changed : (!bt || wp || valid || !ready));
        new_clear=rst || a || (waiting ? changed : (!bt || valid || !ready));
        if(old_clear !== new_clear) $fatal(1,"clear fourstate mismatch vector=%0d",i);
        clear_vectors=clear_vectors+1;
    end
    $display("FOURSTATE_PASS abort_vectors=%0d clear_vectors=%0d",abort_vectors,clear_vectors);
    $finish;
end
endmodule
