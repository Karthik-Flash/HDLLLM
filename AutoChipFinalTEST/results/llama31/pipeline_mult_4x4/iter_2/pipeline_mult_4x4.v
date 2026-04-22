module pipeline_mult_4x4 (
  input clk,
  input [3:0] a, b,
  output reg [7:0] product
);

reg [3:0] a_r, b_r;

always @(posedge clk) begin
  a_r     <= a;           // Stage 1: latch inputs
  b_r     <= b;
  product <= a_r * b_r;   // Stage 2: multiply the latched values
end

endmodule