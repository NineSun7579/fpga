// Created by IP Generator (Version 2022.2-SP6.4 build 146967)
// Instantiation Template
//
// Insert the following codes into your Verilog file.
//   * Change the_instance_name to your own instance name.
//   * Change the signal names in the port associations


FIR the_instance_name (
  .i_clk(i_clk),                                // input
  .i_rstn(i_rstn),                              // input
  .i_axi4s_data_tdata(i_axi4s_data_tdata),      // input [7:0]
  .i_axi4s_data_tlast(i_axi4s_data_tlast),      // input
  .o_axi4s_data_tready(o_axi4s_data_tready),    // output
  .i_axi4s_data_tvalid(i_axi4s_data_tvalid),    // input
  .o_axi4s_data_tdata(o_axi4s_data_tdata),      // output [15:0]
  .o_axi4s_data_tlast(o_axi4s_data_tlast),      // output
  .i_axi4s_data_tready(i_axi4s_data_tready),    // input
  .o_axi4s_data_tvalid(o_axi4s_data_tvalid)     // output
);
