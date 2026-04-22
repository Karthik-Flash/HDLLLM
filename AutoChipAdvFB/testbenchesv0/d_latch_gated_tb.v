module d_latch_gated_tb;
    reg  en, d;
    wire q;

    d_latch_gated dut(.en(en),.d(d),.q(q));

    integer fail = 0;

    task check;
        input een, ed;
        input eq;
        begin
            en=een; d=ed; #20;
            if (q !== eq) begin
                $display("FAIL: en=%0d d=%0d -> got q=%0d, exp q=%0d",
                          een, ed, q, eq);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // TEST group 1: latch transparent (en=1, q follows d)
        check(1, 0,  0);
        check(1, 1,  1);
        check(1, 0,  0);
        check(1, 1,  1);

        // TEST group 2: latch closed (en=0, q holds last value)
        // Last value was 1 from above
        check(0, 0,  1);  // d changes to 0, but en=0 so q stays 1
        check(0, 1,  1);  // d=1, en=0, q still 1
        check(0, 0,  1);  // d=0, en=0, q still 1

        // TEST group 3: open latch again -> q catches up to current d
        // d is 0 currently
        check(1, 0,  0);  // now q should follow d=0
        check(1, 1,  1);

        // TEST group 4: close again and hold
        // Last value was 1
        check(0, 0,  1);  // d=0, en=0, q holds 1

        // TEST group 5: open briefly to load 0, then close
        check(1, 0,  0);  // latch open, q=0
        check(0, 1,  0);  // latch closed, d=1 but q stays 0
        check(0, 0,  0);  // q still 0

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
