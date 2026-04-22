module full_adder (
    input a,
    input b,
    input cin,
    output sum,
    output cout
);

wire sum;
wire cout;

assign sum  = a ^ b ^ cin;
assign cout = (a & b) | (b & cin) | (a & cin);

endmodule