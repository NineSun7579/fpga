config full_config;
    design `RX_LIB.tb_sfp_full;
    default liblist `RX_LIB `TX_LIB;
    instance tb_sfp_full.tx use `TX_LIB.sfp_video_tx;
    instance tb_sfp_full.tx.u_fifo use `TX_LIB.video_async_fifo;
    instance tb_sfp_full.split.u_fifo5 use `RX_LIB.video_async_fifo;
    instance tb_sfp_full.split.u_fifo6 use `RX_LIB.video_async_fifo;
endconfig
