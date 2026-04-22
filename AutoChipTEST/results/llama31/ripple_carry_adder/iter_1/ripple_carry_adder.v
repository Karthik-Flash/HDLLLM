module ripple_carry_adder (
    input [3:0] A,
    input [3:0] B,
    input cin,
    output wire [3:0] Sum,
    output wire cout
);

wire [4:0] fa0_sum, fa1_sum, fa2_sum, fa3_sum;

full_adder fa0 (
    .a(A[0]),
    .b(B[0]),
    .cin(cin),
    .sum(fa0_sum[0]),
    .cout(fa0_sum[1])
);

full_adder fa1 (
    .a(A[1]),
    .b(B[1]),
    .cin(fa0_sum[1]),
    .sum(fa1_sum[0]),
    .cout(fa1_sum[1])
);

full_adder fa2 (
    .a(A[2]),
    .b(B[2]),
    .cin(fa1_sum[1]),
    .sum(fa2_sum[0]),
    .cout(fa2_sum[1])
);

full_adder fa3 (
    .a(A[3]),
    .b(B[3]),
    .cin(fa2_sum[1]),
    .sum(fa3_sum[0]),
    .cout(fa3_sum[1])
);

assign Sum = {fa3_sum[0], fa2_sum[0], fa1_sum[0], fa0_sum[0]};
assign cout = fa3_sum[1];

endmodule