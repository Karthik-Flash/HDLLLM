module param_register_file (
  clk,
  wr_en,
  wr_addr,
  rd_addr,
  wr_data,
  rd_data
);

  parameter N = 4;
  parameter W = 8;

  reg [W-1:0] mem [0:N-1];

  input clk;
  input wr_en;
  input [1:0] wr_addr;
  input [1:0] rd_addr;
  input [W-1:0] wr_data;
  output wire [W-1:0] rd_data;

  always @(posedge clk) if (wr_en) mem[wr_addr] <= wr_data;

  assign rd_data = mem[rd_addr];

endmodule