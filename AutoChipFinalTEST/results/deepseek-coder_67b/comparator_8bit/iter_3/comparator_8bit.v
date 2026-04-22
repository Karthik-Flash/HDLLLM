module comparator_8bit(input [7:0] A, B, output reg gt, eq, lt);
  
  assign gt = (A > B);
  assign eq = (A == B);
  assign lt = (A < B);
  
endmodule