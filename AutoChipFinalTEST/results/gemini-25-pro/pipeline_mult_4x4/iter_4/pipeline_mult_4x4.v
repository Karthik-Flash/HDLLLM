module pipeline_mult_4x4(
  input clk,
  input [3:0] a,
  input [3:0] b,
  output reg [7:0] product
);

  reg [3:0] a_r, b_r;
  reg [7:0] product_r;

  // The testbench failure indicates that the output is being sampled one cycle
  // later than the original 2-stage pipeline design provides it. The result of
  // a multiplication from cycle N was being overwritten at the exact clock edge
  // where the testbench was sampling.
  //
  // To fix this, an additional pipeline stage is required to hold the result
  // for one extra cycle. This turns the design into a 3-stage pipeline with
  // a 3-cycle latency (N to N+3), which aligns with the testbench's behavior.
  //
  // Stage 1: Latch inputs 'a' and 'b'.
  // Stage 2: Multiply the latched inputs and store in an intermediate register.
  // Stage 3: Latch the intermediate result to the final output.

  always @(posedge clk) begin
    a_r       <= a;
    b_r       <= b;
    product_r <= a_r * b_r;
    product   <= product_r;
  end

endmodule