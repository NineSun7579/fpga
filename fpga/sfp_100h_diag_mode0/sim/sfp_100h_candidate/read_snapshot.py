"""Host helper only: caller supplies existing read32/write32, no board imports."""
NAMES=['signature_mode_flags','skip_delete_cycles','skip_add_cycles','raw_k2_words',
 'raw_k4_words','phase_changes','last_frame_disparity_error_cycles','last_frame_decode_error_cycles',
 'last_decoded_frame_pixels','raw_k0_pixels_between_decoded_sofs','bc_k_50_d_pairs',
 'bc_k_28_d_pairs','status_error_cycles','parser_overflow_cycles','link_losses','decoded_sofs']
def read_snapshot(read32,write32,base=0x20000000):
    write32(base+0x1d0,0x100)
    seq=read32(base+0x1f0)
    values=[]
    for index in range(16):
        write32(base+0x1d0,index)
        values.append(read32(base+0x1e0))
    if read32(base+0x1f0)!=seq:
        raise RuntimeError('snapshot changed: concurrent capture/read access')
    return dict(capture_seq=seq,**dict(zip(NAMES,values)))
