module simple_cpu_top (
    input clk,
    input rst,
    input [7:0] instruction,
    output [3:0] result,
    output zero
);

    wire [1:0] alu_op;
    wire we_reg;
    wire [2:0] rs1, rs2, rd;
    wire [3:0] A, B;

    simple_cpu_ctrl ctrl (
        .clk(clk),
        .rst(rst),
        .instruction(instruction),
        .alu_op(alu_op),
        .we_reg(we_reg),
        .rs1(rs1),
        .rs2(rs2),
        .rd(rd)
    );

    simple_cpu_regfile rf (
        .clk(clk),
        .rst(rst),
        .we(we_reg),
        .waddr(rd),
        .raddr1(rs1),
        .raddr2(rs2),
        .wdata(result),
        .rdata1(A),
        .rdata2(B)
    );

    simple_cpu_alu alu (
        .A(A),
        .B(B),
        .op(alu_op),
        .result(result),
        .zero(zero)
    );

endmodule