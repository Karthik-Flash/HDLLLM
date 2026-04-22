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

    reg [3:0] regfile [0:3];

    // Sync reset
    always @(posedge clk or posedge rst) begin
        if (rst)
            regfile[0] <= 4'b0000;
        else if (we)
            regfile[waddr] <= wdata;
    end

    // Async read
    assign rdata1 = regfile[raddr1];
    assign rdata2 = regfile[raddr2];

endmodule