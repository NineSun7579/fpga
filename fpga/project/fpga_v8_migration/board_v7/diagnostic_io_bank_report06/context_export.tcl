set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "CLI_PROJECT_CONTEXT_EXPORT_ONLY"
export_fdc -file {context_roundtrip.fdc}
puts "CLI_PROJECT_CONTEXT_EXPORT_COMPLETE"
