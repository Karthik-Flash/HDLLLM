module simple_cpu_ctrl (
    input clk,
    input rst,
    input [7:0] instruction,
    output reg [1:0] alu_op,
    output reg we_reg,
    output reg [1:0] rs1,
    output reg [1:0] rs2,
    output reg [1:0] rd
);

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            alu_op <= 2'b00;
            we_reg <= 1'b0;
            rs1 <= 2'b00;
            rs2 <= 2'b00;
            rd <= 2'b00;
        end else begin
            // Decode the instruction and set the control signals
            case (instruction[7:6])
                2'b00: begin
                    alu_op <= 2'b00; // Example operation
                    we_reg <= 1'b1;
                    rs1 <= instruction[5:4];
                    rs2 <= instruction[3:2];
                    rd <= instruction[1:0];
                end
                // Add more cases as needed
                default: begin
                    alu_op <= 2'b00;
                    we_reg <= 1'b0;
                    rs1 <= 2'b00;
                    rs2 <= 2'b00;
                    rd <= 2'b00;
                end
            endcase
        end
    end

endmodule