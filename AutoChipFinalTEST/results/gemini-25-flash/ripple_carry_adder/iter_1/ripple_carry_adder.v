module ripple_carry_adder (
    input [3:0] A,
    input [3:0] B,
    input cin,
    output [3:0] Sum,
    output cout
);

    // Declare outputs as wire as they are driven by sub-module output ports
    wire [3:0] Sum;
    wire cout;

    // Declare internal wires for carry propagation
    wire c1, c2, c3;

    // Instantiate four full_adder modules
    // fa0 handles the least significant bit (LSB)
    full_adder fa0 (
        .a    (A[0]),
        .b    (B[0]),
        .cin  (cin),
        .sum  (Sum[0]),
        .cout (c1)
    );

    // fa1 handles the next bit, receiving carry from fa0
    full_adder fa1 (
        .a    (A[1]),
        .b    (B[1]),
        .cin  (c1),
        .sum  (Sum[1]),
        .cout (c2)
    );

    // fa2 handles the next bit, receiving carry from fa1
    full_adder fa2 (
        .a    (A[2]),
        .b    (B[2]),
        .cin  (c2),
        .sum  (Sum[2]),
        .cout (c3)
    );

    // fa3 handles the most significant bit (MSB), receiving carry from fa2
    // Its carry-out becomes the module's final carry-out
    full_adder fa3 (
        .a    (A[3]),
        .b    (B[3]),
        .cin  (c3),
        .sum  (Sum[3]),
        .cout (cout)
    );

endmodule