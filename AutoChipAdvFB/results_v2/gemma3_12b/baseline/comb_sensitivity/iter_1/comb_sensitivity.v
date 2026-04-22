module comb_sensitivity (
  input a,
  input b,
  input c,
  input sel,
  output reg out
);

  always @(a, b, c, sel) begin
    if (sel == 1'b0) begin
      out = a & b;
    end else begin
      out = b | c;
    end
  end

endmodule