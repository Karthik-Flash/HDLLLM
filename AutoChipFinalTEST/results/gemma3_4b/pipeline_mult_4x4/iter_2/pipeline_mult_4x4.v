module pipeline_mult_4x4 (
  input clk,
  input [3:0] a,
  input [3:0] b,
  output reg [7:0] product
);

  reg [3:0] a_r, b_r;

  always @(posedge clk) begin
    a_r     <= a;
    b_r     <= b;
    product <= a_r * b_r;
  end

endmodule