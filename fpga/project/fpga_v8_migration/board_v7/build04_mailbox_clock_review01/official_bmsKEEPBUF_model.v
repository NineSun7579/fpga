module bmsKEEPBUF ( Z, I ); // pragma PAP_LIB_BMS_PRIM_OPERATOR

    parameter WIDTH = 2;

    output [WIDTH - 1 : 0] Z;
    input  [WIDTH - 1 : 0] I;

// pragma translate_off
    assign Z = I;
// pragma translate_on

endmodule