module alu_accumulator_top (
    input clk,
    input rst,
    input [7:0] data_in,
    input [2:0] op,
    input load_acc,
    output wire [7:0] acc_out,
    output wire zero
);

    wire [7:0] alu_result;
    reg [7:0] acc;

    always @(posedge clk) begin
        if (rst) begin
            acc <= 8'h00;
        end else if (load_acc) begin
            acc <= data_in;
        end else begin
            acc <= alu_result;
        end
    end

    assign acc_out = acc;
    assign zero = (acc == 8'h00) ? 1 : 0;

endmodule