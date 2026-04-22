module seq_detector_101_tb;
    reg  clk, rst, in;
    wire detected;

    seq_detector_101 dut(.clk(clk),.rst(rst),.in(in),.detected(detected));

    always #5 clk = ~clk;

    integer fail = 0;

    task apply;
        input b;
        begin
            @(negedge clk); in = b;
        end
    endtask

    task do_reset;
        begin
            rst = 1; in = 0;
            @(posedge clk); #1;
            rst = 0;
        end
    endtask

    initial begin
        clk = 0; rst = 0;
        do_reset;

        // TEST 1: basic 1-0-1 -> detect
        apply(1); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;
        if (detected !== 1'b1) begin
            $display("FAIL T1: 1-0-1 not detected (got %0d)", detected);
            fail = fail + 1;
        end

        do_reset;

        // TEST 2: 1-1-1 -> no detect
        apply(1); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;
        if (detected !== 1'b0) begin
            $display("FAIL T2: 1-1-1 falsely detected (got %0d)", detected);
            fail = fail + 1;
        end

        do_reset;

        // TEST 3: 1-0-0 -> no detect
        apply(1); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        if (detected !== 1'b0) begin
            $display("FAIL T3: 1-0-0 falsely detected (got %0d)", detected);
            fail = fail + 1;
        end

        do_reset;

        // TEST 4: 0-1-0-1 -> detect on last bit
        apply(0); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;
        if (detected !== 1'b1) begin
            $display("FAIL T4: 0-1-0-1 not detected (got %0d)", detected);
            fail = fail + 1;
        end

        do_reset;

        // TEST 5: overlapping 1-0-1-0-1 -> detect at bit 3 AND bit 5
        apply(1); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;  // first detection here
        if (detected !== 1'b1) begin
            $display("FAIL T5a: overlap first detect missed (got %0d)", detected);
            fail = fail + 1;
        end
        apply(0); @(posedge clk); #1;
        apply(1); @(posedge clk); #1;  // second detection (overlapping)
        if (detected !== 1'b1) begin
            $display("FAIL T5b: overlap second detect missed (got %0d)", detected);
            fail = fail + 1;
        end

        do_reset;

        // TEST 6: reset mid-sequence clears state
        apply(1); @(posedge clk); #1;
        apply(0); @(posedge clk); #1;
        do_reset;                       // reset before the final 1
        apply(1); @(posedge clk); #1;
        if (detected !== 1'b0) begin
            $display("FAIL T6: mid-reset state not cleared (got %0d)", detected);
            fail = fail + 1;
        end

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
