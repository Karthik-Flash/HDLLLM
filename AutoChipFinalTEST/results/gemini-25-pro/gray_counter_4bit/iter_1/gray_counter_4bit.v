module gray_counter_4bit (
  input clk,
  input rst,
  output wire [3:0] gray_out
);

  reg [3:0] bin;

  // Internal 4-bit binary up-counter, synchronous active-high reset
  always @(posedge clk) begin
    if (rst)
      bin <= 4'b0;
    else
      bin <= bin + 1'b1;
  end

  // Gray encode the binary count
  assign gray_out = bin ^ (bin >> 1);

endmodule