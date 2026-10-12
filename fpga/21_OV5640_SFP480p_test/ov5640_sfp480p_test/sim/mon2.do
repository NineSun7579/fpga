log -r /*
when {sim:/tb_cam2_merge/dut/a_ready[0] == 1 or sim:/tb_cam2_merge/dut/a_ready[1] == 1 or sim:/tb_cam2_merge/dut/state == 3'd1 and sim:/tb_cam2_merge/dut/a_rcnt == 0} {
  echo [monitor] $now a_page=%d a_cur=%d r0=%b r1=%b awcnt=%d state=%d
}
run 250 us
quit -f
