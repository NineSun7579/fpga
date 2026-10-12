from pathlib import Path
import difflib
here=Path(__file__).resolve().parent
old=here.parent/'cdc_boundary_candidate'
root=here.parents[1]/'whole_candidate_v7_route_01'
def derive(src,name,changes):
    raw=src.read_bytes(); out=raw
    for a,b in changes:
        assert a in out,a
        out=out.replace(a,b)
    (here/name).write_bytes(out)
    (here/(name+'.diff')).write_text(''.join(difflib.unified_diff(raw.decode('latin1').splitlines(True),out.decode('latin1').splitlines(True),fromfile=str(src),tofile=name)),encoding='utf8')
derive(old/'cdc_order_candidate.v','cdc_recovery.v',[
 (b'module cdc_order_candidate',b'module cdc_recovery'),
 (b'parameter DATA_WIDTH = 24',b'parameter DATA_WIDTH = 16'),
 (b'output boundary_fault,',b'output boundary_fault,\n    input system_reset,'),
 (b'wire full = pixel_full || meta_full || transport_fault || violation;',b'wire full = (s_valid && pixel_full) || meta_full || transport_fault || violation;\n'+(here/'recovery.vh').read_bytes()),
 (b'wire put = event_token && !full;',b'wire put = event_token && !full && source_ready && accept_epoch;'),
 (b'always @(posedge cam_clk or posedge cam_rst) begin\n      if(cam_rst) begin vs_seen<=0;transport_fault<=0;end',b'always @(posedge cam_clk or posedge system_reset) begin\n      if(system_reset) transport_fault<=0;\n      else if(source_ready && accept_epoch && event_token && full) transport_fault<=1;\n    end\n    always @(posedge cam_clk or posedge cam_clear) begin\n      if(cam_clear) begin vs_seen<=0;end'),
 (b'        if(event_token && full) transport_fault<=1;',b''),
 (b'!meta_empty && !fault_sync[1]',b'!meta_empty && !fault_sync[1] && !isolate && !video_clear && cam_ready_video[1]'),
 (b'.wr(cam_rst)',b'.wr(cam_clear)'),(b'.rr(video_rst)',b'.rr(video_clear)'),
 (b'.wr_rst(cam_rst)',b'.wr_rst(cam_clear)'),(b'.rd_rst(video_rst)',b'.rd_rst(video_clear)'),
 (b'always @(posedge video_clk or posedge video_rst)',b'always @(posedge video_clk or posedge video_clear)'),
 (b'if(video_rst) begin',b'if(video_clear) begin'),
 (b'assign boundary_fault=fault_sync[1];',b'assign boundary_fault=reset_fault | transport_fault | request_reset;'),
 (b'assign video_valid=video_valid_r;',b'assign video_valid=video_valid_r && !isolate && !video_clear;'),
 (b'assign video_vsync=vs_level;',b'assign video_vsync=vs_level && !isolate && !video_clear;')])
derive(root/'rtl/ov5640_ddr_tc04.v','ddr_recovery.v',[
 (b'module ov5640_ddr_tc04',b'module ddr_recovery'),
 (b'input dma_abort,',b'input dma_abort,\n    input transport_abort,'),
 (b'wire frame_good = capture_complete && !capture_bad && !capture_overflow;',b'wire frame_good = capture_complete && !capture_bad && !capture_overflow && !transport_abort;'),
 (b'wire capture_stop = capture_flush || capture_bad || capture_complete;',b'wire capture_stop = capture_flush || capture_bad || capture_complete || transport_abort;'),
 (b'assign dma_abort_req = capture_bad;',b'assign dma_abort_req = capture_bad | transport_abort;'),
 (b'if(dma_abort ||',b'if(transport_abort || dma_abort ||'),
 (b'.engine_busy(engine_busy | capture_flush)',b'.engine_busy(engine_busy | capture_flush | transport_abort)'),
 (b'ov5640_ddr_w_ctrl #(',b'ddr_ctrl_recovery #('),
 (b'.dma_abort(dma_abort)',b'.dma_abort(dma_abort | transport_abort)')])
derive(root/'inputs/source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v','ddr_ctrl_recovery.v',[
 (b'module ov5640_ddr_w_ctrl',b'module ddr_ctrl_recovery'),
 (b'wire publish = dma_done &&',b'wire publish = !dma_abort && dma_done &&'),
 (b'wire frame_done = dma_done &&',b'wire frame_done = !dma_abort && dma_done &&'),
 (b'        case (curr_state)',b'        if(dma_abort) next_state = IDLE;\n        else case (curr_state)'),
 (b'else if(axi_vsync_rise &&',b'else if(dma_abort) vsync_pending <= 0;\n        else if(axi_vsync_rise &&'),
 (b'            if((curr_state == IDLE) && vsync_pending)begin\n                axi_cmd_valid',b'            if(dma_abort) axi_cmd_valid <= 0;\n            else if((curr_state == IDLE) && vsync_pending)begin\n                axi_cmd_valid')])
(here/'cdc_order_meta.v').write_bytes((old/'cdc_order_meta.v').read_bytes())
print('generated isolated CDC/wrapper/controller derivatives')
