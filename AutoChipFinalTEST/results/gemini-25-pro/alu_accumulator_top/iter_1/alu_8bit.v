module alu_8bit (
  input  [7:0] A,
  input  [7:0] B,
  input  [2:0] op,
  output reg [7:0] result,
  output wire  zero
);

  always @(*) begin
    case (op)
      3'b000: result = A + B;
      3'b001: result = A - B;
      3'b010: result = A & B;
      3'b011: result = A | B;
      3'b100: result = A ^ B;
      3'b101: result = ~A;
      3'b110: result = A << 1;
      3'b111: result = A >> 1;
      default: result = 8'h00;
    endcase
  end

  assign zero = (result == 8'h00);

endmodule