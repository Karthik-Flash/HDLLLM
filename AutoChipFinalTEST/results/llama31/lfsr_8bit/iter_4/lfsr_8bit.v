module lfsr_8bit (
    input clk,
    input rst,
    input load,
    input enable,
    input [7:0] seed,
    output reg [7:0] lfsr_out
);

always @(posedge clk)
begin
    if (rst)          lfsr_out <= 8'hFF;
    else if (load)    lfsr_out <= seed;
    else if (enable)  // Galois right-shift with XOR feedback:
       lfsr_out <= {lfsr_out[0], lfsr_out[7:6], lfsr_out[5]^lfsr_out[0],
                    lfsr_out[4]^lfsr_out[0], lfsr_out[3]^lfsr_out[0],
                    lfsr_out[2]};
    else              lfsr_out <= lfsr_out; // hold (no change)
end

endmodule