module simple_cpu_ctrl_tb;
    reg clk, rst;
    reg [7:0] instruction;
    wire [1:0] alu_op;
    wire we_reg;
    wire [1:0] rs1, rs2, rd;
    integer fail = 0;

    simple_cpu_ctrl uut(.clk(clk),.rst(rst),.instruction(instruction),
                        .alu_op(alu_op),.we_reg(we_reg),.rs1(rs1),.rs2(rs2),.rd(rd));

    initial clk=0;
    always #5 clk=~clk;

    task check;
        input [1:0] exp_op;
        input exp_we;
        input [31:0] tid;
        begin
            #1;
            if(alu_op!==exp_op || we_reg!==exp_we) begin
                $display("FAIL test%0d: instr=%b | got op=%b we=%b | exp op=%b we=%b",
                    tid,instruction,alu_op,we_reg,exp_op,exp_we);
                fail=fail+1;
            end else $display("PASS test%0d",tid);
        end
    endtask

    initial begin
        rst=1; instruction=8'h00; @(posedge clk); #1; rst=0;
        instruction=8'b000_00_00_0; check(2'b00, 0, 1);
        instruction=8'b001_01_10_0; check(2'b00, 1, 2);
        instruction=8'b010_10_01_0; check(2'b01, 1, 3);
        instruction=8'b011_00_11_0; check(2'b10, 1, 4);
        instruction=8'b100_11_00_0; check(2'b11, 1, 5);
        instruction=8'b111_00_00_0; check(2'b00, 0, 6);
        if(fail==0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED",fail);
        $finish;
    end
endmodule
