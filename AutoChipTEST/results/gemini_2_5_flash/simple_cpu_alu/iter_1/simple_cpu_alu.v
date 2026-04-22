module simple_cpu_alu (
    input [3:0] A,
    input [3:0] B,
    input [1:0] op,
    output [3:0] result,
    output zero
);

    // result is declared as reg because it is assigned inside an always block.
    reg [3:0] result;

    // zero is declared as wire because it is assigned using an assign statement.
    wire zero;

    // Combinational logic for the ALU operations
    always @(*) begin
        case (op)
            2'b00: result = A + B; // ADD
            2'b01: result = A - B; // SUB
            2'b10: result = A & B; // AND
            2'b11: result = A | B; // OR
            default: result = 4'bxxxx; // Default case to avoid latches and handle undefined op codes
        endcase
    end

    // Assign the zero flag based on the computed result
    assign zero = (result == 4'b0000);

endmodule