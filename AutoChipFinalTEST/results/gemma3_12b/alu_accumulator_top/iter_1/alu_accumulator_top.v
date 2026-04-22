module alu_accumulator_top (
  input clk,
  input rst,
  input [7:0] data_in,
  input [2:0] op,
  input load_acc,
  output wire [7:0] acc_out,
  output wire zero
);

  wire [7:0] alu_result;

  reg [7:0] acc;

  alu_8bit u_alu (
    .A(acc_out),
    .B(data_in),
    .op(op),
    .result(alu_result),
    .zero(zero)
  );

  always @(posedge clk) begin
    if (rst)
      acc <= 8'h00;
    else if (load_acc)
      acc <= data_in;
    else
      acc <= alu_result;
  end

  assign acc_out = acc;

endmodule