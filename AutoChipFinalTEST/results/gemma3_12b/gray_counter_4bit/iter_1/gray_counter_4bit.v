module gray_counter_4bit (
  input clk,
  input rst,
  output wire [3:0] gray_out
);

  reg [3:0] bin;

  always @(posedge clk) begin
    if (rst)
      bin <= 4'b0;
    else
      bin <= bin + 1'b1;
  end

  assign gray_out = bin ^ (bin >> 1);

endmodule