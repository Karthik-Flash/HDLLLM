module dff_sync_reset (
  input clk,
  input rst,
  input d,
  output reg q
);

always @(posedge clk)
if (rst) begin
  q <= 0;
end else begin
  q <= d;
end

endmodule