module simple_cpu_alu(input [3:0] A, B, input [1:0] op, output reg [3:0] result, output wire zero);
  always @* begin
    case (op)
      2'b00 : // ADD operation
        begin
          result = A + B;
          $display("Result of addition is %d", result);
        end
      2'b01 : // SUBTRACT operation
        begin
          result = A - B;
          $display("Result of subtraction is %d", result);
        end
      2'b10 : // AND operation
        begin
          result = A & B;
          $display("Result of AND operation is %d", result);
        end
      2'b11 : // OR operation
        begin
          result = A | B;
          $display("Result of OR operation is %d", result);
        end
      default: $display("Invalid Operation");
    endcase
  end
  
  assign zero = (result == 4'b0000) ? 1 : 0; // Assigning value to 'zero' based on the condition
endmodule