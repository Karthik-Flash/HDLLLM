module alu_accumulator_top(
    input clk, rst, load_acc,
    input  [7:0] data_in,
    input  [2:0] op,
    output reg [7:0] acc_out,
    output wire zero
);
    
    // Internal wires and registers
    wire [7:0] alu_result;
    reg [7:0] acc = 8'h00;
  
    // Instantiate  'alu_8bit'
    alu_8bit u_alu(
        .A(acc), 
        .B(data_in), 
        .op(op), 
        .result(alu_result), 
        .zero(zero)
    );
  
    // Accumulator register
    always @(posedge clk or posedge rst) begin
        if (rst) acc <= 8'h00;
        else if (load_acc) acc <= data_in;
        else acc <= alu_result;
    end
  
    assign acc_out = acc;
    
endmodule