module lfsr_8bit (
    input clk,
    input rst,
    input load,
    input enable,
    input [7:0] seed,
    output reg [7:0] lfsr_out
);

always @(posedge clk) begin
    if (rst)
        lfsr_out <= 8'hFF;
    else if (load)
        lfsr_out <= seed;
    else if (enable)
        lfsr_out <= {
            lfsr_out[0],              // new bit[7] = feedback
            lfsr_out[7:6],            // bit[6:5]  plain shift
            lfsr_out[5]^lfsr_out[0],  // bit[4]    tap x^6
            lfsr_out[4]^lfsr_out[0],  // bit[3]    tap x^5
            lfsr_out[3]^lfsr_out[0],  // bit[2]    tap x^4
            lfsr_out[2:1]             // bit[1:0]  plain shift
        };
end

endmodule