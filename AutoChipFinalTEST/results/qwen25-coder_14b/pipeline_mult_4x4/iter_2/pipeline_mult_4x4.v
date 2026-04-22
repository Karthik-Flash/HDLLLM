module pipeline_mult_4x4 (
    input clk,
    input [3:0] a,
    input [3:0] b,
    output reg [7:0] product
);

reg [3:0] a_r, b_r;
reg [7:0] product_r;

always @(posedge clk) begin
    a_r     <= a;           // Stage 1: latch inputs
    b_r     <= b;
    product_r <= a_r * b_r;   // Stage 2: multiply the latched values
    product <= product_r;   // Output the result from stage 2
end

endmodule