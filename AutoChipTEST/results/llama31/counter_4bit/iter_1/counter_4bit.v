module counter_4bit(
    input clk,
    input rst,
    output [3:0] count
);

reg [3:0] count;

always @(posedge clk)
if (rst) begin
    count <= 0;
end else begin
    count <= count + 1;
end

endmodule