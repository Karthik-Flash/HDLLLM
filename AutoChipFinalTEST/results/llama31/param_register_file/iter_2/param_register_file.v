module param_register_file #(
  parameter N = 4,
  parameter W = 8
) (
  input clk,
  input wr_en,
  input  [1:0]   rd_addr, // corrected port name
  input  [W-1:0] wr_data,
  output wire [W-1:0] rd_data
);
reg [W-1:0] mem [0:N-1];

always @(posedge clk) if (wr_en) mem[wr_addr] <= wr_data;

assign rd_data = mem[rd_addr];
endmodule