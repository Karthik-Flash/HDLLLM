module ripple_carry_adder (
  input [3:0] A,
  input [3:0] B,
  input cin,
  output [3:0] Sum,
  output cout
);

  wire [3:0] fa0_sum, fa1_sum, fa2_sum, fa3_sum;
  wire fa0_cout, fa1_cout, fa2_cout, fa3_cout;

  full_adder fa0 (
    .a(A[0]),
    .b(B[0]),
    .cin(cin),
    .sum(fa0_sum[0]),
    .cout(fa0_cout)
  );

  full_adder fa1 (
    .a(A[1]),
    .b(B[1]),
    .cin(fa0_cout),
    .sum(fa1_sum[1]),
    .cout(fa1_cout)
  );

  full_adder fa2 (
    .a(A[2]),
    .b(B[2]),
    .cin(fa1_cout),
    .sum(fa2_sum[2]),
    .cout(fa2_cout)
  );

  full_adder fa3 (
    .a(A[3]),
    .b(B[3]),
    .cin(fa2_cout),
    .sum(fa3_sum[3]),
    .cout(fa3_cout)
  );

  assign Sum[0] = fa0_sum[0];
  assign Sum[1] = fa1_sum[1];
  assign Sum[2] = fa2_sum[2];
  assign Sum[3] = fa3_sum[3];

  assign cout = fa3_cout;
  assign fa0.cin = cin;
  assign fa3.cout = cout;

endmodule