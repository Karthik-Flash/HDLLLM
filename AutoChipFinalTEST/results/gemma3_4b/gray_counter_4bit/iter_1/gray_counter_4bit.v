module gray_counter_4bit (
  input clk,
  input rst,
  output wire [3:0] gray_out
);

  reg [3:0] bin;
  wire [3:0] gray_out_wire;

  always @(posedge clk) begin
    if (rst) begin
      bin <= 4'b0;
    end else begin
      bin <= bin + 1'b1;
    end
  end

  assign gray_out_wire = bin ^ (bin >> 1);
  assign gray_out = gray_out_wire;

endmodule