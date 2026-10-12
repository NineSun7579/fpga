# TA -tcl script: enumerate only; no reporting, mutation, PNR or prerequisites.
# Requires a fresh mapped ADF containing sys_rst_sync and diag_rst_sync.
get_pins -hierarchical {u_sfp_video_tx/u_fifo/mem_*/ram32x1dp/WCLK}
get_pins -hierarchical {u_sfp_video_tx/u_fifo/mem_*/ram32x1dp/RD}
get_pins -hierarchical {u_sfp_video_tx/head_q*/I*}
get_pins -hierarchical {u_sfp_video_tx/head_q*/S*}
get_pins -hierarchical {u_sfp_video_tx/u_fifo/wptr_rd1*/D}
get_pins -hierarchical {u_sfp_video_tx/u_fifo/rptr_wr1*/D}
get_pins -hierarchical {sys_rst_sync*/RS}
get_pins -hierarchical {diag_rst_sync*/RS}
get_clocks cfg_clk
get_clocks mrg_clk
get_clocks p_clk2core_tx_2
