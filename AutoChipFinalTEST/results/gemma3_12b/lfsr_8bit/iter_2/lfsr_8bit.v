module lfsr_8bit (
    input clk,
    input rst,
    input load,
    input enable,
    input [7:0] seed,
    output reg [7:0] lfsr_out
);

  always @(posedge clk) begin
    if (rst) begin
      lfsr_out <= 8'hFF;
    end else if (load) begin
      lfsr_out <= seed;
    end else if (enable) begin
      lfsr_out <= {
          lfsr_out[0],
          lfsr_out[7:6],
          lfsr_out[5]^lfsr_out[0],
          lfsr_out[4]^lfsr_out[0],
          lfsr_out[3]^lfsr_out[0],
          lfsr_out[2:1]
      };
    end else begin
      lfsr_out <= lfsr_out;
    end
  end

endmodule