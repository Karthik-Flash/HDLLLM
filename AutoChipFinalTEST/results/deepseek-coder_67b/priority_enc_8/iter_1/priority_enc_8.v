```verilog
module priority_enc_8 (input [7:0] in, output reg [2:0] out, output wire valid);
  
  assign valid = |in;    // continuous assign, valid is a wire
  
  always @(*) begin     // combinational always block
    if      (in[7]) out = 3'd7;
    else if (in[6]) out = 3'd6;
    else if (in[5]) out = 3'd5;<beginofsentence>