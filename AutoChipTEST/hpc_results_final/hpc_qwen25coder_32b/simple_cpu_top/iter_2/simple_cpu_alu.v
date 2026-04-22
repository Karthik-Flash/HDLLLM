module simple_cpu_alu (
    input [3:0] A,
    input [3:0] B,
    input [1:0] op,
    output [3:0] result,
    output wire zero
);

reg [3:0] result_reg;
wire [3:0] result_wire;

localparam ADD = 2'b00;
localparam SUB = 2'b01;
localparam AND = 2'b10;
localparam OR  = 2'b11;

always @(*) begin
    case (op)
        ADD: result_wire = A + B;
        SUB: result_wire = A - B;
        AND: result_wire = A & B;
        OR:  result_wire = A | B;
        default: result_wire = 4'b0000;
    endcase
end

always @(posedge clk or posedge reset) begin
    if (reset)
        result_reg <= 4'b0000;
    else
        result_reg <= result_wire;
end

assign result = result_reg;
assign zero = (result_reg == 4'b0000);

endmodule