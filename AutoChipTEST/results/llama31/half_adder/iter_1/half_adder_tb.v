module half_adder_tb;
    reg a, b;
    wire sum, cout;
    integer fail = 0;

    half_adder uut (.a(a), .b(b), .sum(sum), .cout(cout));

    task check;
        input exp_sum, exp_cout;
        input [7:0] test_id;
        begin
            #1;
            if (sum !== exp_sum || cout !== exp_cout) begin
                $display("FAIL test%0d: a=%b b=%b | got sum=%b cout=%b | expected sum=%b cout=%b",
                    test_id, a, b, sum, cout, exp_sum, exp_cout);
                fail = fail + 1;
            end else
                $display("PASS test%0d", test_id);
        end
    endtask

    initial begin
        {a,b} = 2'b00; check(0, 0, 1);
        {a,b} = 2'b01; check(1, 0, 2);
        {a,b} = 2'b10; check(1, 0, 3);
        {a,b} = 2'b11; check(0, 1, 4);
        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
