module simple_cpu_alu (input [3:0] A, B, input [1:0] op, output reg [3:0] result, output wire zero);
  always @(*) begin
    case (op)
      2'b00 : result = A + B; // ADD operation
      2'b01 : result = A - B; // SUBTRACT operation
      2'b10 : result = A & B; // AND operation
      2'b11 : result = A | B; // OR operation
      default: result = 4'b0;  // Default case, set result to zero
    endcase
  end
  assign zero = (result == 4'b0); // Assign the value of zero based on whether result is zero or not
endmodule