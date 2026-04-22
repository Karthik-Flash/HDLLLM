module ripple_carry_adder (
  input [3:0] A,
  input [3:0] B,
  input cin,
  output [3:0] Sum,
  output cout
);

  wire fa0_cout, fa1_cout, fa2_cout;

  full_adder fa0 (
    .a(A[0]),
    .b(B[0]),
    .cin(cin),
    .sum(Sum[0]),
    .cout(fa0_cout)
  );

  full_adder fa1 (
    .a(A[1]),
    .b(B[1]),
    .cin(fa0_cout),
    .sum(Sum[1]),
    .cout(fa1_cout)
  );

  full_adder fa2 (
    .a(A[2]),
    .b(B[2]),
    .cin(fa1_cout),
    .sum(Sum[2]),
    .cout(fa2_cout)
  );

  full_adder fa3 (
    .a(A[3]),
    .b(B[3]),
    .cin(fa2_cout),
    .sum(Sum[3]),
    .cout(cout)
  );

endmodule

module full_adder (
  input a,
  input b,
  input cin,
  output sum,
  output cout
);

  assign sum = a ^ b ^ cin;
  assign cout = (a & b) | (a & cin) | (b & cin);

endmodule