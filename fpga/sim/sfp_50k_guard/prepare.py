from pathlib import Path
import re,hashlib,json,difflib
R=Path(__file__).resolve().parent;W=R.parents[2]
T=W/'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
original=(T/'sfp_video_tx.v').read_bytes()
(R/'original_sfp_video_tx.v').write_bytes(original)
b=original
b=b.replace(b'module sfp_video_tx (',b'module sfp_video_tx #(parameter TX_GE_SKIP_ENABLE=1) (')
# Only producer assignment targets change; ports retain exact external ABI.
for signal in ['txd','txk']:
 b=re.sub(rb'\b'+signal.encode()+rb'(\s*<=)',signal.encode()+b'_producer'+rb'\1',b)
insert=b'''
    // Isolated 50K guard experiment. Three-word lookahead; FIFO pops unchanged.
    reg [31:0] txd_producer, gd0,gd1,gd2;
    reg [3:0] txk_producer, gk0,gk1,gk2;
    reg [31:0] last_ctrl;
    reg [4:0] idle_phase;
    wire redundant=(gk2==9 && gd2==last_ctrl);
    wire following_controls=(gk1==9 && gk0==9 && txk_producer==9 &&
        gd1==gd2 && gd0==gd2 && txd_producer==gd2);
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if(!fab_rst_n) begin
            gd0<=32'hbc0028bc;gd1<=32'hbc0028bc;gd2<=32'hbc0028bc;
            gk0<=9;gk1<=9;gk2<=9;last_ctrl<=32'hbc0028bc;idle_phase<=0;
            txd<=32'hbc0028bc;txk<=9;
        end else if(!payload_go) begin
            // Drop queued wire words on lost readiness, just as producer does.
            gd0<=consume_head?ctrl_word:idle_word;gd1<=consume_head?ctrl_word:idle_word;
            gd2<=consume_head?ctrl_word:idle_word;gk0<=9;gk1<=9;gk2<=9;
            txd<=consume_head?ctrl_word:idle_word;txk<=9;
            last_ctrl<=consume_head?ctrl_word:idle_word;idle_phase<=0;
        end else begin
            gd0<=txd_producer;gd1<=gd0;gd2<=gd1;
            gk0<=txk_producer;gk1<=gk0;gk2<=gk1;
            idle_phase<=idle_phase+1'b1;
            txd<=gd2;txk<=gk2;
            // The guard contains valid K28.5/D31.7 bytes; old RX ignores K=5.
            // Ending in D removes trailing-control K28.5 -> payload D16.2.
            if(redundant && gk1==0) begin txd<=32'hffbcffbc;txk<=5;end
            // Dedicated configured GE skip pairs, well before next payload.
            // Two complete BC/28 controls remain for old phase reacquisition.
            else if(TX_GE_SKIP_ENABLE && redundant && following_controls && idle_phase==0 && gd2[22:21]==0)
                begin txd<=32'h50bc50bc;txk<=5;end
            if(gk2==9)last_ctrl<=gd2;
        end
    end
'''
assert b.count(b'    // [CTC FIX]')==1
b=b.replace(b'    // [CTC FIX]',insert+b'    // [CTC FIX]')
(R/'candidate_sfp_video_tx.v').write_bytes(b)
(R/'guard_only_sfp_video_tx.v').write_bytes(b.replace(b'parameter TX_GE_SKIP_ENABLE=1',b'parameter TX_GE_SKIP_ENABLE=0'))
(R/'integration.patch').write_bytes(b''.join(difflib.diff_bytes(difflib.unified_diff,original.splitlines(True),b.splitlines(True),fromfile=b'a/sfp_video_tx.v',tofile=b'b/sfp_video_tx.v')))
manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [T/'sfp_video_tx.v',T/'hdmi_ddr_ov5640_top.v',W/'project/source/sfp/sfp_rx_link.v',W/'project/source/sfp/sfp_video_rx.v',W/'project/ipcore/hsst_sfp/hsst_sfp.v']}
(R/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Prepared isolated 50K guard/skip TX; production and IP untouched')
