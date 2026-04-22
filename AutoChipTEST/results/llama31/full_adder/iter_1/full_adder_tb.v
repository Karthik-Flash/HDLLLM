module full_adder_tb;
    reg a, b, cin;
    wire sum, cout;
    integer fail = 0;

    full_adder uut (.a(a), .b(b), .cin(cin), .sum(sum), .cout(cout));

    task check;
        input exp_sum, exp_cout;
        input [7:0] test_id;
        begin
            #1;
            if (sum !== exp_sum || cout !== exp_cout) begin
                $display("FAIL test%0d: a=%b b=%b cin=%b | got sum=%b cout=%b | expected sum=%b cout=%b",
                    test_id, a, b, cin, sum, cout, exp_sum, exp_cout);
                fail = fail + 1;
            end else
                $display("PASS test%0d", test_id);
        end
    endtask

    initial begin
        {a,b,cin} = 3'b000; check(0, 0, 1);
        {a,b,cin} = 3'b001; check(1, 0, 2);
        {a,b,cin} = 3'b010; check(1, 0, 3);
        {a,b,cin} = 3'b011; check(0, 1, 4);
        {a,b,cin} = 3'b100; check(1, 0, 5);
        {a,b,cin} = 3'b101; check(0, 1, 6);
        {a,b,cin} = 3'b110; check(0, 1, 7);
        {a,b,cin} = 3'b111; check(1, 1, 8);
        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
