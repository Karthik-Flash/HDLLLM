module dff_sync_reset (
    input wire clk,
    input wire rst,
    input wire d,
    output reg q
);

always @(posedge clk) begin
    if (rst)
        q <= 0;
    else
        q <= d;
end

endmodule