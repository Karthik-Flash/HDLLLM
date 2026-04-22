module dff_sync_reset_tb;
    reg clk, rst, d;
    wire q;
    integer fail = 0;

    dff_sync_reset uut (.clk(clk), .rst(rst), .d(d), .q(q));

    initial clk = 0;
    always #5 clk = ~clk;

    task posedge_check;
        input exp_q;
        input [31:0] tid;
        begin
            @(posedge clk); #1;
            if (q !== exp_q) begin
                $display("FAIL test%0d: rst=%b d=%b | got q=%b | expected q=%b", tid, rst, d, q, exp_q);
                fail = fail + 1;
            end else
                $display("PASS test%0d", tid);
        end
    endtask

    initial begin
        rst=1; d=1; posedge_check(0, 1);  // reset overrides d
        rst=1; d=0; posedge_check(0, 2);  // reset holds
        rst=0; d=1; posedge_check(1, 3);  // d captured
        rst=0; d=0; posedge_check(0, 4);  // d captured
        rst=0; d=1; posedge_check(1, 5);
        rst=1; d=1; posedge_check(0, 6);  // sync reset clears
        rst=0; d=1; posedge_check(1, 7);  // normal operation
        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
