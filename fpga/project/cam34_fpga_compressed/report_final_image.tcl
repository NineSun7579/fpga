set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
report_timing -input_db_file {D:/race/ov56401/project/cam34_fpga_compressed/project/place_route/top_pnr.adf} -force_to_run -delay_type min_max -nworst 1 -max_path 120 -input_pins TRUE
