set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_ONLY"
show_device -device CLMA -file {clma_devices.txt}
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_COMPLETE"
