module comparator_8bit (
    input [7:0] A,
    input [7:0] B,
    output wire gt,
    output wire eq,
    output wire lt
);

assign gt = (A > B);
assign eq = (A == B);
assign lt = (A < B);

endmodule