config recovery_config;
    design `RX_LIB.tb_tx_recovery;
    default liblist `RX_LIB `TX_LIB;
    instance tb_tx_recovery.tx use `TX_LIB.sfp_video_tx;
    instance tb_tx_recovery.tx.u_fifo use `TX_LIB.video_async_fifo;
endconfig
