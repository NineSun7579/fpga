// Created by IP Generator (Version 2022.2-SP6.4 build 146967)
// Instantiation Template
//
// Insert the following codes into your Verilog file.
//   * Change the_instance_name to your own instance name.
//   * Change the signal names in the port associations


DebugCore the_instance_name (
  .hub_tdi(hub_tdi),      // input
  .hub_tdo(hub_tdo),      // output
  .id_i(id_i),            // input [4:0]
  .capt_i(capt_i),        // input
  .shift_i(shift_i),      // input
  .conf_sel(conf_sel),    // input
  .drck_in(drck_in),      // input
  .clk(clk),              // input
  .resetn_i(resetn_i),    // input
  .data_i(data_i),        // input [63:0]
  .trig0_i(trig0_i)       // input
);
