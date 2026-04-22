module full_adder(input a, b, cin, output reg sum, cout);
  assign sum  = a ^ b ^ cin;    // sum
  assign cout = (a & b) | (b & cin) | (a & cin);   // carry out
endmodule