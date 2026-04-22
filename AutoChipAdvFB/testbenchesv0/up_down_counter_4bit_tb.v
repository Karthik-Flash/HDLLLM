module up_down_counter_4bit_tb;
    reg        clk, rst, load, up, down;
    reg  [3:0] d;
    wire [3:0] q;

    up_down_counter_4bit dut(
        .clk(clk),.rst(rst),.load(load),
        .up(up),.down(down),.d(d),.q(q)
    );

    always #5 clk = ~clk;

    integer fail = 0;

    task tick;
        begin @(posedge clk); #1; end
    endtask

    initial begin
        clk=0; rst=1; load=0; up=0; down=0; d=0;
        tick; rst=0;

        // TEST 1: synchronous load
        d=4'd7; load=1; tick; load=0;
        if (q !== 4'd7) begin
            $display("FAIL T1: load 7, got %0d", q); fail=fail+1;
        end

        // TEST 2: count up x3 (7->8->9->10)
        up=1; tick; tick; tick; up=0;
        if (q !== 4'd10) begin
            $display("FAIL T2: up x3 from 7, got %0d", q); fail=fail+1;
        end

        // TEST 3: count down x2 (10->9->8)
        down=1; tick; tick; down=0;
        if (q !== 4'd8) begin
            $display("FAIL T3: down x2 from 10, got %0d", q); fail=fail+1;
        end

        // TEST 4: synchronous reset overrides everything
        up=1; rst=1; tick; rst=0; up=0;
        if (q !== 4'd0) begin
            $display("FAIL T4: rst did not clear (got %0d)", q); fail=fail+1;
        end

        // TEST 5: load takes priority over up when both asserted
        d=4'd5; load=1; up=1; tick; load=0; up=0;
        if (q !== 4'd5) begin
            $display("FAIL T5: load vs up priority, got %0d", q); fail=fail+1;
        end

        // TEST 6: overflow wrap-around (15 + 1 = 0)
        d=4'd15; load=1; tick; load=0;
        up=1; tick; up=0;
        if (q !== 4'd0) begin
            $display("FAIL T6: overflow 15->0, got %0d", q); fail=fail+1;
        end

        // TEST 7: underflow wrap-around (0 - 1 = 15)
        down=1; tick; down=0;
        if (q !== 4'd15) begin
            $display("FAIL T7: underflow 0->15, got %0d", q); fail=fail+1;
        end

        // TEST 8: up and down simultaneously -> hold (no change)
        d=4'd3; load=1; tick; load=0;
        up=1; down=1; tick; up=0; down=0;
        if (q !== 4'd3) begin
            $display("FAIL T8: up+down simultaneously, got %0d (exp 3)", q);
            fail=fail+1;
        end

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
