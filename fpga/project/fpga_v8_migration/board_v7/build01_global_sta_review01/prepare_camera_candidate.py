"""Generate byte-preserving isolated golden/candidate copies and provenance."""
from pathlib import Path
import hashlib,json,difflib
HERE=Path(__file__).resolve().parent
BUILD=HERE.parent/'source_diagnostics_timing_build_01'
DEST=HERE/'camera_boolean_candidate01'
DEST.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
sources={n:(BUILD/'rtl'/n).read_bytes() for n in ['v7_sfd_candidate.v','ov5640_cdc_tc04.v']}
changes={}
for name,raw in sources.items():
    candidate=raw
    if name=='v7_sfd_candidate.v':
        old=b'else if(clear) prefix[i]<=0;\n                else prefix[i]<=(&q[i*4-1:1]) & (q[0]^inc);'
        new=b'else prefix[i]<=((&q[i*4-1:1]) & (q[0]^inc)) & !clear;'
        assert candidate.count(old)==1;candidate=candidate.replace(old,new)
        old=b'else if(clear) begin\n                if(i==0) q[i*4+:4]<={3\'b0,seed};\n                else q[i*4+:4]<=0;\n            end else q[i*4+:4]<=next_q[i*4+:4];'
        new=b'''else if(i==0) q[i*4+:4] <= (next_q[i*4+:4] & {4{!clear}}) | {3'b0,(clear & seed)};
            else q[i*4+:4] <= next_q[i*4+:4] & {4{!clear}};'''
        assert candidate.count(old)==1;candidate=candidate.replace(old,new)
        # Specialize only cg: keep the half-cycle frame signal at final gates.
        old=b'''v7_sfd_counter #(.W(16)) cg(cam_clk,rst_c,edge_vs | href,1'b0,
        count_on & seen_href & !href & !(&gap_q),gap_q,);'''
        new=b'''v7_camera_gap_boolean cg(cam_clk,rst_c,capture_vsync,vs_q,href,
        count_on & seen_href & !href & !(&gap_q),gap_q);'''
        assert candidate.count(old)==1;candidate=candidate.replace(old,new)
        candidate+=b'''
// Clear priority is unchanged. Late capture_vsync enters final bit gates only.
module v7_camera_gap_boolean(input clk,rst,frame_vs,old_vs,href,inc,
    output reg [15:0] q);
    reg [3:1] prefix;
    genvar s,b;
    generate for(s=0;s<4;s=s+1) begin: slices
        wire carry;
        if(s==0) assign carry=inc;
        else begin
            assign carry=inc & prefix[s];
            wire prefix_pred=(&q[s*4-1:1]) & (q[0]^inc);
            always @(posedge clk or posedge rst)
                if(rst) prefix[s]<=0;
                else prefix[s]<=prefix_pred & !href & (!frame_vs | old_vs);
        end
        for(b=0;b<4;b=b+1) begin: bits
            wire toggle_bit;
            if(b==0) assign toggle_bit=carry;
            else assign toggle_bit=carry & (&q[s*4+b-1:s*4]);
            wire predicted_bit=q[s*4+b] ^ toggle_bit;
            always @(posedge clk or posedge rst)
                if(rst) q[s*4+b]<=0;
                else q[s*4+b]<=predicted_bit & !href & (!frame_vs | old_vs);
        end
    end endgenerate
endmodule
'''
        golden=raw.replace(b'v7_sfd_counter',b'golden_sfd_counter').replace(b'v7_sfd_candidate',b'golden_sfd')
        candidate=candidate.replace(b'v7_sfd_counter',b'candidate_sfd_counter').replace(b'v7_sfd_candidate',b'candidate_sfd')
    else:
        old=b'''end else if (src_frame_start) begin
                    // New count is only 0 or 1, so every >=4-bit prefix is false.
                    count_prefix[stat_slice] <= 0;
                    drop_prefix[stat_slice] <= 0;
                end else begin
                    count_prefix[stat_slice] <= (&src_count[stat_slice*4-1:1]) && (src_count[0] ^ s_valid);
                    drop_prefix[stat_slice] <= (&src_drop[stat_slice*4-1:1]) && (src_drop[0] ^ drop_increment);
                end'''
        new=b'''end else begin
                    count_prefix[stat_slice] <= ((&src_count[stat_slice*4-1:1]) && (src_count[0] ^ s_valid)) & (!s_vsync | src_vs_q);
                    drop_prefix[stat_slice] <= ((&src_drop[stat_slice*4-1:1]) && (src_drop[0] ^ drop_increment)) & (!s_vsync | src_vs_q);
                end'''
        assert candidate.count(old)==1;candidate=candidate.replace(old,new)
        golden=raw.replace(b'ov5640_cdc_tc04',b'golden_cdc')
        candidate=candidate.replace(b'ov5640_cdc_tc04',b'candidate_cdc')
    (DEST/('golden_'+name)).write_bytes(golden)
    (DEST/('candidate_'+name)).write_bytes(candidate)
    changes[name]={'source':str(BUILD/'rtl'/name),'original_sha256':sha(raw),'golden_sha256':sha(golden),'candidate_sha256':sha(candidate),'encoding':'original bytes retained; ASCII literal replacements only'}
    (DEST/(name+'.diff')).write_bytes(b''.join(difflib.diff_bytes(difflib.unified_diff, golden.splitlines(True),candidate.splitlines(True),fromfile=b'golden',tofile=b'candidate')))
(DEST/'provenance.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf8')
print(json.dumps(changes,indent=2))
