module simple_cpu_top_tb;
    reg clk, rst;
    reg [7:0] instruction;
    wire [3:0] result;
    wire zero;
    integer fail = 0;

    simple_cpu_top uut(.clk(clk),.rst(rst),.instruction(instruction),
                       .result(result),.zero(zero));

    initial clk=0;
    always #5 clk=~clk;

    initial begin
        rst=1; instruction=8'h00;
        @(posedge clk); #1; rst=0;

        // ADD r0+r1
        instruction=8'b001_00_01_0;
        @(posedge clk); #1;
        $display("ADD r0+r1 = %0d", result);

        // NOP
        instruction=8'b000_00_00_0;
        @(posedge clk); #1;

        // AND r0&r1
        instruction=8'b011_00_01_0;
        @(posedge clk); #1;
        $display("AND r0&r1 = %0d", result);

        if(zero===1'bx) begin
            $display("FAIL: zero flag is X"); fail=fail+1;
        end else $display("PASS zero flag defined");

        if(result===4'bxxxx) begin
            $display("FAIL: result is X"); fail=fail+1;
        end else $display("PASS result defined");

        if(fail==0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED",fail);
        $finish;
    end
endmodule
