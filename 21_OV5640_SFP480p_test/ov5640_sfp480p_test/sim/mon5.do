log -r /*
when {sim:/tb_cam2_merge/dut/apop == 1} {
  echo APOP $now rdata=%h fcnt=%d
}
run 130 us
quit -f
