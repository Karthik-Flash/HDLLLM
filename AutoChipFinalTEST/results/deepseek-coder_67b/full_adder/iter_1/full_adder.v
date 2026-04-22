module full_adder (input a, b, cin, output reg [1:0] out);
  assign out[0] = a ^ b ^ cin; // sum
  assign out[1] = (a & b) | (b & cin) | (a & cin); // cout
endmodule