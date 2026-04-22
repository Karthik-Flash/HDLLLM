module pipeline_mult_4x4(input clk, input [3:0] a, b, output reg [7:0] product);
  reg [3:0] a_r, b_r;
  
  always @(posedge clk) begin
    a_r <= a; // Stage 1: latch inputs
    b_r <= b;
    
    #2 product <= {4'b0, a_r} * {4'b0, b_r}; // Stage 2: multiply the latched values after 2 cycles delay
  end
endmodule