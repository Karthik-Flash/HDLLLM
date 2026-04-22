module lfsr_8bit(input clk, rst, load, enable, input  [7:0] seed, output reg [7:0] lfsr_out);
  always @(posedge clk) begin
    if (rst)
      lfsr_out <= 8'hFF;
    else if (load)
      lfsr_out <= seed;
    else if (enable)
      lfsr_out <= {lfsr_out[6:0], lfsr_out[7] ^ lfsr_out[0]};   // XOR feedback with lfsr_out[7]
  end
endmodule