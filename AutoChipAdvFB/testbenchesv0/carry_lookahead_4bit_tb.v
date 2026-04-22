module carry_lookahead_4bit_tb;
    reg  [3:0] a, b;
    reg        cin;
    wire [3:0] sum;
    wire       cout;

    carry_lookahead_4bit dut(.a(a),.b(b),.cin(cin),.sum(sum),.cout(cout));

    integer fail = 0;

    task check;
        input [3:0] ta, tb;
        input       tc;
        input [3:0] esum;
        input       ecout;
        begin
            a=ta; b=tb; cin=tc; #10;
            if (sum !== esum || cout !== ecout) begin
                $display("FAIL: %0d+%0d+cin%0d = got sum=%0d cout=%0d | exp sum=%0d cout=%0d",
                          ta,tb,tc,sum,cout,esum,ecout);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // Basic additions
        check(4'd0,  4'd0,  0,  4'd0,  0);
        check(4'd1,  4'd1,  0,  4'd2,  0);
        check(4'd5,  4'd3,  0,  4'd8,  0);
        check(4'd7,  4'd7,  0,  4'd14, 0);
        check(4'd9,  4'd6,  0,  4'd15, 0);

        // Carry-in cases
        check(4'd0,  4'd0,  1,  4'd1,  0);
        check(4'd1,  4'd1,  1,  4'd3,  0);
        check(4'd7,  4'd7,  1,  4'd15, 0);

        // Overflow / cout cases
        check(4'd8,  4'd8,  0,  4'd0,  1);   // 8+8=16
        check(4'd9,  4'd7,  0,  4'd0,  1);   // 9+7=16
        check(4'd15, 4'd1,  0,  4'd0,  1);   // 15+1=16
        check(4'd15, 4'd15, 0,  4'd14, 1);   // 30 -> sum=14,cout=1
        check(4'd15, 4'd15, 1,  4'd15, 1);   // 31 -> sum=15,cout=1
        check(4'd9,  4'd7,  1,  4'd1,  1);   // 9+7+1=17

        // Lookahead-specific: all carries propagate (all 1s)
        check(4'd1,  4'd14, 0,  4'd15, 0);
        check(4'd7,  4'd8,  1,  4'd0,  1);   // 7+8+1=16

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
