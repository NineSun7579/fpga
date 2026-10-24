# Opaque handles must never be measured with llength.
# Acceptance requires Python verify_console over captured TA stdout.
set c5_overlay_checked 0
puts "C5_SELECT_BEGIN s0"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/commands/req_sync(\[[0-9:]+\])?/D\[0\]$)|(^runtime/commands/req_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s0 $rc"
puts "C5_SELECT_BEGIN s1"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/commands/ack_sync(\[[0-9:]+\])?/D\[0\]$)|(^runtime/commands/ack_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s1 $rc"
puts "C5_SELECT_BEGIN s2"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/commands/held(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^runtime/commands/held\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s2 $rc"
puts "C5_SELECT_BEGIN s3"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/commands/d_data(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^runtime/commands/d_data\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s3 $rc"
puts "C5_SELECT_BEGIN s4"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/responses/req_sync(\[[0-9:]+\])?/D\[0\]$)|(^runtime/responses/req_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s4 $rc"
puts "C5_SELECT_BEGIN s5"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/responses/ack_sync(\[[0-9:]+\])?/D\[0\]$)|(^runtime/responses/ack_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s5 $rc"
puts "C5_SELECT_BEGIN s6"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/responses/held(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^runtime/responses/held\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s6 $rc"
puts "C5_SELECT_BEGIN s7"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/responses/d_data(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^runtime/responses/d_data\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s7 $rc"
puts "C5_SELECT_BEGIN s8"
set rc [catch {get_pins -hierarchical -regexp {(^metadata/req_sync(\[[0-9:]+\])?/D\[0\]$)|(^metadata/req_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s8 $rc"
puts "C5_SELECT_BEGIN s9"
set rc [catch {get_pins -hierarchical -regexp {(^metadata/ack_sync(\[[0-9:]+\])?/D\[0\]$)|(^metadata/ack_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s9 $rc"
puts "C5_SELECT_BEGIN s10"
set rc [catch {get_pins -hierarchical -regexp {(^metadata/held(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^metadata/held\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s10 $rc"
puts "C5_SELECT_BEGIN s11"
set rc [catch {get_pins -hierarchical -regexp {(^metadata/d_data(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^metadata/d_data\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s11 $rc"
puts "C5_SELECT_BEGIN s12"
set rc [catch {get_pins -hierarchical -regexp {(^initial_en_sync(\[[0-9:]+\])?/D\[0\]$)|(^initial_en_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s12 $rc"
puts "C5_SELECT_BEGIN s13"
set rc [catch {get_pins -hierarchical -regexp {(^mode_mrg(\[[0-9:]+\])?/D\[0\]$)|(^mode_mrg\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s13 $rc"
puts "C5_SELECT_BEGIN s14"
set rc [catch {get_pins -hierarchical -regexp {(^mode_a(\[[0-9:]+\])?/D\[0\]$)|(^mode_a\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s14 $rc"
puts "C5_SELECT_BEGIN s15"
set rc [catch {get_pins -hierarchical -regexp {(^mode_b(\[[0-9:]+\])?/D\[0\]$)|(^mode_b\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s15 $rc"
puts "C5_SELECT_BEGIN s16"
set rc [catch {get_pins -hierarchical -regexp {(^epoch_active_mrg(\[[0-9:]+\])?/D\[0\]$)|(^epoch_active_mrg\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s16 $rc"
puts "C5_SELECT_BEGIN s17"
set rc [catch {get_pins -hierarchical -regexp {(^runtime/fault_sync(\[[0-9:]+\])?/D\[0\]$)|(^runtime/fault_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s17 $rc"
puts "C5_SELECT_BEGIN s18"
set rc [catch {get_pins -hierarchical -regexp {(^u_mode/request_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_mode/request_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s18 $rc"
puts "C5_SELECT_BEGIN s19"
set rc [catch {get_pins -hierarchical -regexp {(^u_mode/fault_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_mode/fault_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s19 $rc"
puts "C5_SELECT_BEGIN s20"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/ready_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_hdmi_capture/ready_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s20 $rc"
puts "C5_SELECT_BEGIN s21"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/lock_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_hdmi_capture/lock_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s21 $rc"
puts "C5_SELECT_BEGIN s22"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/ready_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_sfp_video_tx/ready_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s22 $rc"
puts "C5_SELECT_BEGIN s23"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fault_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_sfp_video_tx/fault_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s23 $rc"
puts "C5_SELECT_BEGIN s24"
set rc [catch {get_pins -hierarchical -regexp {(^u_hd_merge/a_pages/fault_sync(\[[0-9:]+\])?/D\[0\]$)|(^u_hd_merge/a_pages/fault_sync\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s24 $rc"
puts "C5_SELECT_BEGIN s26"
set rc [catch {get_pins -hierarchical -regexp {(^u_hsst/.*word_align_sync/sig_async_ff/D\[0\]$)|(^u_hsst/.*word_align_sync/sig_async_ff/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s26 $rc"
puts "C5_SELECT_BEGIN s27"
set rc [catch {get_pins -hierarchical -regexp {(^.*/release_q\[0\]/C$)|(^.*/release_q\[0\]/opit_0(_inv|_srl)?/RS$)}} msg]
puts "C5_SELECT_END s27 $rc"
puts "C5_SELECT_BEGIN s28"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_afifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_cam2_merge/u_afifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s28 $rc"
puts "C5_SELECT_BEGIN s29"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_afifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_cam2_merge/u_afifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s29 $rc"
puts "C5_SELECT_BEGIN s30"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_afifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_cam2_merge/u_afifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s30 $rc"
puts "C5_SELECT_BEGIN s31"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_afifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_cam2_merge/u_afifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s31 $rc"
puts "C5_SELECT_BEGIN s32"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_afifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_cam2_merge/u_afifo/.*mem.*/ram32x1dp_inv/RD$)}} msg]
puts "C5_SELECT_END s32 $rc"
puts "C5_SELECT_BEGIN s33"
set rc [catch {get_clocks {mrg_clk}} msg]
puts "C5_SELECT_END s33 $rc"
puts "C5_SELECT_BEGIN s34"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_bfifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_cam2_merge/u_bfifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s34 $rc"
puts "C5_SELECT_BEGIN s35"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_bfifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_cam2_merge/u_bfifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s35 $rc"
puts "C5_SELECT_BEGIN s36"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_bfifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_cam2_merge/u_bfifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s36 $rc"
puts "C5_SELECT_BEGIN s37"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_bfifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_cam2_merge/u_bfifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s37 $rc"
puts "C5_SELECT_BEGIN s38"
set rc [catch {get_pins -hierarchical -regexp {(^u_cam2_merge/u_bfifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_cam2_merge/u_bfifo/.*mem.*/ram32x1dp_inv/RD$)}} msg]
puts "C5_SELECT_END s38 $rc"
puts "C5_SELECT_BEGIN s39"
set rc [catch {get_clocks {mrg_clk}} msg]
puts "C5_SELECT_END s39 $rc"
puts "C5_SELECT_BEGIN s40"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/u_fifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_hdmi_capture/u_fifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s40 $rc"
puts "C5_SELECT_BEGIN s41"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/u_fifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_hdmi_capture/u_fifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s41 $rc"
puts "C5_SELECT_BEGIN s42"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/u_fifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_hdmi_capture/u_fifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s42 $rc"
puts "C5_SELECT_BEGIN s43"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/u_fifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_hdmi_capture/u_fifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s43 $rc"
puts "C5_SELECT_BEGIN s44"
set rc [catch {get_pins -hierarchical -regexp {(^u_hdmi_capture/u_fifo/g_bank\[[0-9]+\]\.g_group\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_hdmi_capture/u_fifo/.*mem.*/ram32x1dp_inv/RD$)}} msg]
puts "C5_SELECT_END s44 $rc"
puts "C5_SELECT_BEGIN s45"
set rc [catch {get_clocks {mrg_clk}} msg]
puts "C5_SELECT_END s45 $rc"
puts "C5_SELECT_BEGIN s46"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_sfp_video_tx/fifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s46 $rc"
puts "C5_SELECT_BEGIN s47"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_sfp_video_tx/fifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s47 $rc"
puts "C5_SELECT_BEGIN s48"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_sfp_video_tx/fifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s48 $rc"
puts "C5_SELECT_BEGIN s49"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_sfp_video_tx/fifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s49 $rc"
puts "C5_SELECT_BEGIN s50"
set rc [catch {get_pins -hierarchical -regexp {(^u_sfp_video_tx/fifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_sfp_video_tx/fifo/g_bank\[[0-9]+\]\.mem/iGopDrm_inv/DO(A|B)\[[0-9]+\]$)}} msg]
puts "C5_SELECT_END s50 $rc"
puts "C5_SELECT_BEGIN s51"
set rc [catch {get_clocks {p_clk2core_tx_2}} msg]
puts "C5_SELECT_END s51 $rc"
puts "C5_SELECT_BEGIN s52"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_wr_fifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_wr_fifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s52 $rc"
puts "C5_SELECT_BEGIN s53"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_wr_fifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_wr_fifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s53 $rc"
puts "C5_SELECT_BEGIN s54"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_wr_fifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_wr_fifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s54 $rc"
puts "C5_SELECT_BEGIN s55"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_wr_fifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_wr_fifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s55 $rc"
puts "C5_SELECT_BEGIN s56"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_wr_fifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_temporal/u_state/u_wr_fifo/.*mem.*/ram32x1dp_inv/RD$)}} msg]
puts "C5_SELECT_END s56 $rc"
puts "C5_SELECT_BEGIN s57"
set rc [catch {get_clocks {ddrphy_clkin}} msg]
puts "C5_SELECT_END s57 $rc"
puts "C5_SELECT_BEGIN s58"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_rq_fifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_rq_fifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s58 $rc"
puts "C5_SELECT_BEGIN s59"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_rq_fifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_rq_fifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s59 $rc"
puts "C5_SELECT_BEGIN s60"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_rq_fifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_rq_fifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s60 $rc"
puts "C5_SELECT_BEGIN s61"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_rq_fifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_rq_fifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s61 $rc"
puts "C5_SELECT_BEGIN s62"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_rq_fifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_temporal/u_state/u_rq_fifo/.*mem.*/ram16x1d_inv/RD$)}} msg]
puts "C5_SELECT_END s62 $rc"
puts "C5_SELECT_BEGIN s63"
set rc [catch {get_clocks {ddrphy_clkin}} msg]
puts "C5_SELECT_END s63 $rc"
puts "C5_SELECT_BEGIN s64"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_completion_fifo/wptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_completion_fifo/wptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s64 $rc"
puts "C5_SELECT_BEGIN s65"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_completion_fifo/wptr_rd1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_completion_fifo/wptr_rd1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s65 $rc"
puts "C5_SELECT_BEGIN s66"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_completion_fifo/rptr(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_temporal/u_state/u_completion_fifo/rptr\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s66 $rc"
puts "C5_SELECT_BEGIN s67"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_completion_fifo/rptr_wr1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_temporal/u_state/u_completion_fifo/rptr_wr1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s67 $rc"
puts "C5_SELECT_BEGIN s68"
set rc [catch {get_pins -hierarchical -regexp {(^u_temporal/u_state/u_completion_fifo/g_bank\[[0-9]+\]\.mem/(DO|DOA|DOB)(\[[0-9]+\])?$)|(^u_temporal/u_state/u_completion_fifo/.*mem.*/ram16x1d_inv/RD$)}} msg]
puts "C5_SELECT_END s68 $rc"
puts "C5_SELECT_BEGIN s69"
set rc [catch {get_clocks {mrg_clk}} msg]
puts "C5_SELECT_END s69 $rc"
puts "C5_SELECT_BEGIN s70"
set rc [catch {get_pins -hierarchical -regexp {(^u_hd_merge/a_pages/fifo/wgray(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_hd_merge/a_pages/fifo/wgray\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s70 $rc"
puts "C5_SELECT_BEGIN s71"
set rc [catch {get_pins -hierarchical -regexp {(^u_hd_merge/a_pages/fifo/wgray_r1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_hd_merge/a_pages/fifo/wgray_r1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s71 $rc"
puts "C5_SELECT_BEGIN s72"
set rc [catch {get_pins -hierarchical -regexp {(^u_hd_merge/a_pages/fifo/rgray(\[[0-9:]+\])?/Q\[[0-9]+\]$)|(^u_hd_merge/a_pages/fifo/rgray\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END s72 $rc"
puts "C5_SELECT_BEGIN s73"
set rc [catch {get_pins -hierarchical -regexp {(^u_hd_merge/a_pages/fifo/rgray_w1(\[[0-9:]+\])?/D\[[0-9]+\]$)|(^u_hd_merge/a_pages/fifo/rgray_w1\[[0-9]+\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END s73 $rc"
puts "C5_SELECT_BEGIN s74"
set rc [catch {get_cells -hierarchical -regexp {(^u_hd_merge/a_pages/fifo/mem$)|(^u_hd_merge/a_pages/fifo/.*mem.*)}} msg]
puts "C5_SELECT_END s74 $rc"
puts "C5_SELECT_BEGIN c6_scalar"
set rc [catch {get_pins -hierarchical -regexp {(^u_c6_cache/(dfault_s1|sfault_d1|grant_s1|start_d1|end_d1|req_d1|rel_d1|desc_m1|rel_m1|fault_m1)(_vname)?/D(\[0\])?$)|(^u_c6_cache/(dfault_s1|sfault_d1|grant_s1|start_d1|end_d1|req_d1|rel_d1|desc_m1|rel_m1|fault_m1)/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END c6_scalar $rc"
puts "C5_SELECT_BEGIN c6_row_toggles"
set rc [catch {get_pins -hierarchical -regexp {(^u_c6_cache/(ack_s1|row_d1|consume_d1|slot_m1)(\[[0-9:]+\])?/D(\[[01]\])?$)|(^u_c6_cache/(ack_s1|row_d1|consume_d1|slot_m1)\[[01]\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END c6_row_toggles $rc"
puts "C5_SELECT_BEGIN c6_outer_controls"
set rc [catch {get_pins -hierarchical -regexp {(^(cache_fault_m|mode_ddr|u_hd_merge/capture_a)(\[[0-9:]+\])?/D\[0\]$)|(^(cache_fault_m|mode_ddr|u_hd_merge/capture_a)\[0\]/D$)|(^(cache_fault_m|mode_ddr|u_hd_merge/capture_a)\[0\]/opit_0(_inv|_srl)?/D$)}} msg]
puts "C5_SELECT_END c6_outer_controls $rc"
puts "C5_SELECT_BEGIN c6_capture_metadata"
set rc [catch {get_pins -hierarchical -regexp {(^u_c6_cache/(capture_sequence|capture_epoch)(\[[0-9:]+\])?/Q(\[[0-9]+\])?$)|(^u_c6_cache/end_good(_vname)?/Q(\[0\])?$)|(^u_c6_cache/capture_y\[[01]\](\[[0-9:]+\])?/Q(\[[0-9]+\])?$)|(^u_c6_cache/(capture_sequence|capture_epoch)\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)|(^u_c6_cache/end_good/opit_0(_inv|_srl)?/Q$)|(^u_c6_cache/capture_y\[[01]\]\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END c6_capture_metadata $rc"
puts "C5_SELECT_BEGIN c6_display_metadata"
set rc [catch {get_pins -hierarchical -regexp {(^u_c6_cache/(descriptor_seq|descriptor_epoch)(\[[0-9:]+\])?/Q(\[[0-9]+\])?$)|(^u_c6_cache/slot_y\[[01]\](\[[0-9:]+\])?/Q(\[[0-9]+\])?$)|(^u_c6_cache/(descriptor_seq|descriptor_epoch)\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)|(^u_c6_cache/slot_y\[[01]\]\[[0-9]+\]/opit_0(_inv|_srl)?/Q$)}} msg]
puts "C5_SELECT_END c6_display_metadata $rc"
puts "C5_SELECT_BEGIN c6_reset_stage0"
set rc [catch {get_pins -hierarchical -regexp {(^u_c6_cache/(sr|dr|mr)\[0\]/C$)|(^u_c6_cache/(sr|dr|mr)\[0\]/opit_0(_inv|_srl)?/RS$)}} msg]
puts "C5_SELECT_END c6_reset_stage0 $rc"
puts "C5_PREFLIGHT_ENUMERATED_EXTERNAL_VERIFICATION_REQUIRED"
