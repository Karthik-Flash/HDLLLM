module register_file_4x8 (
    input clk,
    input we,
    input [1:0] waddr,
    input [1:0] raddr1,
    input [1:0] raddr2,
    input [7:0] wdata,
    output [7:0] rdata1,
    output [7:0] rdata2
);

    reg [7:0] regs [0:3];

    always @(posedge clk) begin
        if (we) begin
            regs[waddr] <= wdata;
        end
    end

    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];

endmodule