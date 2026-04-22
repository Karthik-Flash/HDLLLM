module pipeline_mult_4x4 (
  input clk,
  input [3:0] a, b,
  output reg [7:0] product
);

reg [3:0] a_r, b_r;

always @(posedge clk) begin
  a_r     <= #1 a;           // Stage 1: latch inputs with delay
  b_r     <= #1 b;
  product <= #1 a_r * b_r;   // Stage 2: multiply the latched values with delay
end

endmodule