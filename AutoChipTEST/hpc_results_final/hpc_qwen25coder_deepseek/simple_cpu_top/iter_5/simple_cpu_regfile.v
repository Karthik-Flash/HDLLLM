module simple_cpu_regfile (
    input clk,
    input rst,
    input we,
    input [1:0] waddr,
    input [1:0] raddr1,
    input [1:0] raddr2,
    input [3:0] wdata,
    output [3:0] rdata1,
    output [3:0] rdata2
);

    reg [3:0] registers [0:3];

    // Synchronous write operation
    always @(posedge clk) begin
        if (rst) begin
            registers[0] <= 4'b0000;
            registers[1] <= 4'b0000;
            registers[2] <= 4'b0000;
            registers[3] <= 4'b0000;
        end else if (we) begin
            registers[waddr] <= wdata;
        end
    end

    // Asynchronous read operation
    assign rdata1 = registers[raddr1];
    assign rdata2 = registers[raddr2];

endmodule