set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
add_constraint -physical -pcf {C:/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test/device_map/hdmi_ddr_ov5640_top.pcf}
pnr -input_db_file {C:/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test/physical_flow_proof/proof_map.adf} -force_to_run -place_only
