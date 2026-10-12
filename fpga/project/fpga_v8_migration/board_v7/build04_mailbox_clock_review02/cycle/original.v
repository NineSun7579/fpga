// Isolated diagnostic sideband. No image data ports. DATA_WIDTH=16 / DELAY=2.
// All inputs below are sampled PRE-NBA at posedge cam_clk.
module original_v7_sfd_counter #(parameter W=24) (
    input clk, rst, clear, seed, inc,
    output reg [W-1:0] q,
    output [W-1:0] next_q
);
    // W must be a multiple of four, >= 8. Registered prefix removes the
    // late event from the wide carry path. Modulo counter; caller flags wrap.
    reg [W/4-1:1] prefix;
    genvar i;
    generate for(i=0;i<W/4;i=i+1) begin: slices
        wire carry;
        if(i==0) assign carry=inc;
        else begin
            assign carry=inc & prefix[i];
            always @(posedge clk or posedge rst)
                if(rst) prefix[i]<=0;
                else if(clear) prefix[i]<=0;
                else prefix[i]<=(&q[i*4-1:1]) & (q[0]^inc);
        end
        assign next_q[i*4+:4]=q[i*4+:4]+carry;
        always @(posedge clk or posedge rst)
            if(rst) q[i*4+:4]<=0;
            else if(clear) begin
                if(i==0) q[i*4+:4]<={3'b0,seed};
                else q[i*4+:4]<=0;
            end else q[i*4+:4]<=next_q[i*4+:4];
    end endgenerate
endmodule

module original_v7_sfd_candidate (
    input cam_clk, cam_reset, host_clk, host_reset,
    input raw_vsync, raw_href, raw_byte_accept,
    input capture_vsync, capture_valid,
    // Local host bus: one-cycle read/write strobes, word index, no backpressure.
    // Adapter must latch read_data on read_strobe and retain AXI RDATA itself.
    input read_strobe, acquire_strobe, release_strobe,
    input [4:0] read_word,
    output reg [31:0] read_data,
    output reg read_valid,
    output reg read_error,
    output reg snapshot_valid,
    output snapshot_available,
    output overrun
);
    // Either reset cancels the entire diagnostic session, including a leased
    // host snapshot. Async assert, independent synchronous deassert per clock.
    wire reset_any=cam_reset | host_reset;
    (* ASYNC_REG="TRUE" *) reg [1:0] cr, hr;
    always @(posedge cam_clk or posedge reset_any)
        if(reset_any) cr<=3; else cr<={cr[0],1'b0};
    always @(posedge host_clk or posedge reset_any)
        if(reset_any) hr<=3; else hr<={hr[0],1'b0};
    wire rst_c=cr[1], rst_h=hr[1];
    reg [1:0] raw_vs_d, href_d, accept_d;
    reg valid_d, vs_q, href_q, parity, armed, have_prev;
    reg seen_href, clipped, mismatch, overflowed;
    reg start_aligned, start_native;
    wire vs=raw_vs_d[1], href=href_d[1], byte_en=accept_d[1];
    wire edge_vs=capture_vsync & !vs_q;
    wire seg_inc=href & !href_q;
    wire odd_inc=href_q & !href & parity;
    wire close_odd=href_q & parity; // Boundary also closes a clipped segment.
    wire [23:0] bytes_q, aligned_q, native_q, overlap_q, raw_overlap_q;
    wire [15:0] segments_q, odd_q, odd_next, gap_q;
    wire [31:0] seq_q, seq_next;
    wire count_on=armed;
    original_v7_sfd_counter cb(cam_clk,rst_c,edge_vs,byte_en,count_on & byte_en,bytes_q,);
    original_v7_sfd_counter ca(cam_clk,rst_c,edge_vs,valid_d,count_on & valid_d,aligned_q,);
    original_v7_sfd_counter cn(cam_clk,rst_c,edge_vs,capture_valid,count_on & capture_valid,native_q,);
    original_v7_sfd_counter co(cam_clk,rst_c,edge_vs,capture_valid & capture_vsync,
        count_on & capture_valid & capture_vsync,overlap_q,);
    original_v7_sfd_counter cro(cam_clk,rst_c,edge_vs,byte_en & vs,
        count_on & byte_en & vs,raw_overlap_q,);
    original_v7_sfd_counter #(.W(16)) cs(cam_clk,rst_c,edge_vs,href,
        count_on & seg_inc,segments_q,);
    // next_q includes closure at the boundary; the new frame starts at zero.
    original_v7_sfd_counter #(.W(16)) cod(cam_clk,rst_c,edge_vs,1'b0,
        count_on & (edge_vs ? close_odd : odd_inc),odd_q,odd_next);
    original_v7_sfd_counter #(.W(16)) cg(cam_clk,rst_c,edge_vs | href,1'b0,
        count_on & seen_href & !href & !(&gap_q),gap_q,);
    original_v7_sfd_counter #(.W(32)) cq(cam_clk,rst_c,1'b0,1'b0,
        edge_vs & armed,seq_q,seq_next);

    reg [23:0] prev_bytes, prev_aligned, prev_native;
    reg [15:0] prev_odd, prev_segments;
    reg prev_start_aligned, prev_end_aligned, prev_bad;
    reg request, sticky_overrun;
    reg [511:0] mailbox;
    reg ack;
    (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync;
    wire busy=request != ack_sync[1];
    wire wrap_now=((&bytes_q)&byte_en) | ((&aligned_q)&valid_d) |
        ((&native_q)&capture_valid) | ((&segments_q)&seg_inc) |
        ((&odd_q)&odd_inc) | ((&overlap_q)&capture_valid&capture_vsync) |
        ((&raw_overlap_q)&byte_en&vs);
    wire bad=clipped | mismatch | overflowed |
        (href_q & href) | ((&odd_q)&close_odd);
    always @(posedge cam_clk or posedge rst_c) begin
        if(rst_c) begin
            raw_vs_d<=0; href_d<=0; accept_d<=0; valid_d<=0;
            vs_q<=0; href_q<=0; parity<=0; armed<=0; have_prev<=0;
            seen_href<=0; clipped<=0; mismatch<=0; overflowed<=0;
            start_aligned<=0; start_native<=0;
            prev_bytes<=0; prev_aligned<=0; prev_native<=0;
            prev_odd<=0; prev_segments<=0; prev_start_aligned<=0;
            prev_end_aligned<=0; prev_bad<=0;
            request<=0; sticky_overrun<=0; mailbox<=0; ack_sync<=0;
        end else begin
            raw_vs_d<={raw_vs_d[0],raw_vsync};
            href_d<={href_d[0],raw_href};
            accept_d<={accept_d[0],raw_byte_accept & raw_href};
            valid_d<=capture_valid;
            vs_q<=capture_vsync; href_q<=href;
            ack_sync<={ack_sync[0],ack};
            if(edge_vs) begin
                armed<=1; have_prev<=armed;
                parity<=byte_en; seen_href<=href;
                clipped<=href_q & href;
                mismatch<=capture_vsync != vs;
                overflowed<=0;
                start_aligned<=valid_d; start_native<=capture_valid;
                if(armed) begin
                    prev_bytes<=bytes_q; prev_aligned<=aligned_q;
                    prev_native<=native_q; prev_odd<=odd_next;
                    prev_segments<=segments_q; prev_start_aligned<=start_aligned;
                    prev_end_aligned<=valid_d; prev_bad<=bad;
                    if(busy) sticky_overrun<=1;
                    else begin
                        request<=~request;
                        mailbox[0*32+:32]<=seq_next;
                        mailbox[1*32+:32]<={8'd0,bytes_q};
                        mailbox[2*32+:32]<={16'd0,segments_q};
                        mailbox[3*32+:32]<={16'd0,odd_next};
                        mailbox[4*32+:32]<={8'd0,aligned_q};
                        mailbox[5*32+:32]<={8'd0,native_q};
                        mailbox[6*32+:32]<={8'd0,overlap_q};
                        mailbox[7*32+:32]<={8'd0,bad,overflowed,mismatch,
                            clipped | (href_q & href),(&gap_q),seen_href,have_prev,1'b1,gap_q};
                        mailbox[8*32+:32]<={8'd0,prev_bytes};
                        mailbox[9*32+:32]<={8'd0,prev_aligned};
                        mailbox[10*32+:32]<={8'd0,prev_native};
                        mailbox[11*32+:32]<={16'd0,prev_odd};
                        mailbox[12*32+:32]<={24'd0,prev_bad,prev_end_aligned,
                            prev_start_aligned,href,valid_d,start_aligned,
                            capture_valid,start_native};
                        mailbox[13*32+:32]<={16'd0,prev_segments};
                        mailbox[14*32+:32]<={8'd0,raw_overlap_q};
                        mailbox[15*32+:32]<=32'h53464401;
                    end
                end
            end else begin
                if(!href) parity<=0;
                else if(byte_en) parity<=~parity;
                if(href) seen_href<=1;
                if(armed && capture_vsync != vs) mismatch<=1;
                if(armed && wrap_now) overflowed<=1;
            end
        end
    end

    // Bundled-data handshake: mailbox is written with request, held until ACK.
    // Three synchronizer stages plus a separate capture edge give data settling
    // time. Constrain mailbox->host_bank max delay in eventual integration.
    (* ASYNC_REG="TRUE" *) reg [2:0] req_sync;
    (* ASYNC_REG="TRUE" *) reg [1:0] overrun_sync;
    reg [511:0] host_bank;
    assign overrun=overrun_sync[1];
    assign snapshot_available=!rst_h && !snapshot_valid && (req_sync[2]!=ack);
    always @(posedge host_clk or posedge rst_h) begin
        if(rst_h) begin
            req_sync<=0; overrun_sync<=0; ack<=0;
            host_bank<=0; snapshot_valid<=0; read_valid<=0; read_data<=0; read_error<=0;
        end else begin
            req_sync<={req_sync[1:0],request};
            overrun_sync<={overrun_sync[0],sticky_overrun};
            read_valid<=read_strobe;
            read_error<=read_strobe && ((read_word<16 && !snapshot_valid) || read_word>16);
            if(snapshot_available && acquire_strobe) begin
                host_bank<=mailbox;
                snapshot_valid<=1;
            end else if(snapshot_valid && release_strobe) begin
                ack<=req_sync[2]; snapshot_valid<=0;
            end
            if(read_strobe) begin
                if(read_word==16) read_data<={29'd0,snapshot_available,overrun,snapshot_valid};
                else if(read_word<16 && snapshot_valid)
                    read_data<=host_bank[read_word*32+:32];
                else read_data<=0;
            end
        end
    end
endmodule
