module shift_register_8bit (
    input clk,
    input rst,
    input sin,
    output reg sout,
    output reg [7:0] data
);

always @(posedge clk) begin
    if (rst) begin
        data <= 8'b0;
    end else begin
        data <= {data[6:0], sin};
    end
end

always @(*) begin
    sout = data[7];
end

endmodule