module simple_cpu_alu (
    input [3:0] A,
    input [3:0] B,
    input [1:0] op,
    output reg [3:0] result,
    output wire zero
);

assign zero = (result == 4'b0000);

always @(*) begin
    case (op)
        2'b00: result = A + B;
        2'b01: result = A - B;
        2'b10: result = A & B;
        2'b11: result = A | B;
        default: result = 4'b0000;
    endcase
end

endmodule