module ripple_carry_adder_tb;
    reg  [3:0] A, B;
    reg  cin;
    wire [3:0] Sum;
    wire cout;
    integer fail = 0;
    integer i, j;

    ripple_carry_adder uut (.A(A), .B(B), .cin(cin), .Sum(Sum), .cout(cout));

    task check;
        input [3:0] esum;
        input ecout;
        begin
            #2;
            if (Sum !== esum || cout !== ecout) begin
                $display("FAIL: A=%0d B=%0d cin=%b | got Sum=%0d cout=%b | expected Sum=%0d cout=%b",
                    A, B, cin, Sum, cout, esum, ecout);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // Spot checks
        A=4'd0;  B=4'd0;  cin=0; check(4'd0,  0);
        A=4'd1;  B=4'd1;  cin=0; check(4'd2,  0);
        A=4'd5;  B=4'd3;  cin=0; check(4'd8,  0);
        A=4'd10; B=4'd10; cin=0; check(4'd4,  1);  // 20 = 0b10100 => Sum=4, cout=1
        A=4'd15; B=4'd15; cin=1; check(4'd15, 1);  // 31 = 0b11111 => Sum=15, cout=1
        A=4'd7;  B=4'd8;  cin=1; check(4'd0,  1);  // 16 => Sum=0, cout=1
        A=4'd9;  B=4'd6;  cin=0; check(4'd15, 0);

        // Exhaustive small sweep
        for (i = 0; i < 16; i = i+1) begin
            for (j = 0; j < 16; j = j+1) begin
                A = i; B = j; cin = 0;
                #2;
                if ({cout, Sum} !== (i + j)) begin
                    $display("FAIL exhaustive: A=%0d B=%0d | got {cout,Sum}=%b | expected %0d", i, j, {cout,Sum}, i+j);
                    fail = fail + 1;
                end
            end
        end

        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
