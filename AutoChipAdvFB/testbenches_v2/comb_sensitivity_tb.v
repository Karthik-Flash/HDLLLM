// comb_sensitivity_tb.v
// Module: sel=0 -> out = a & b   sel=1 -> out = b | c
// Spec says "explicit sensitivity list" -> LLMs write @(a, sel) missing b and c
// Verilator: %Warning-UNOPTFLAT or explicit sensitivity warning
// iverilog: FAIL because output doesn't update when b/c change
//
// The critical tests are those that change b or c while a/sel are fixed.
// If b/c are missing from sensitivity list, always block won't re-evaluate.
`timescale 1ns/1ps
module comb_sensitivity_tb;
    reg a, b, c, sel;
    wire out;

    comb_sensitivity dut(.a(a),.b(b),.c(c),.sel(sel),.out(out));

    integer fail = 0;

    task check;
        input ea, eb, ec, esel;
        input eout;
        begin
            a=ea; b=eb; c=ec; sel=esel; #20;
            if (out !== eout) begin
                $display("FAIL a=%0d b=%0d c=%0d sel=%0d: got out=%0d, exp %0d",
                          ea, eb, ec, esel, out, eout);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // ── sel=0: out = a & b ────────────────────────────────────────────
        check(0, 0, 0, 0,  0);  // 0&0=0
        check(1, 0, 0, 0,  0);  // 1&0=0
        check(1, 1, 0, 0,  1);  // 1&1=1

        // CRITICAL: a and sel fixed, only b changes
        // If b not in sensitivity list -> output stuck at 1, won't go to 0
        a=1; sel=0; b=1; c=0; #20;   // expect 1
        if (out!==1) begin $display("FAIL: a=1 b=1 sel=0 -> exp 1, got %0d",out); fail=fail+1; end
        b=0; #20;                      // b changes, output MUST update
        if (out!==0) begin $display("FAIL SENSITIVITY: b changed 1->0 but out still %0d (exp 0)",out); fail=fail+1; end
        b=1; #20;
        if (out!==1) begin $display("FAIL SENSITIVITY: b changed 0->1 but out still %0d (exp 1)",out); fail=fail+1; end

        // ── sel=1: out = b | c ────────────────────────────────────────────
        check(0, 0, 0, 1,  0);  // 0|0=0
        check(0, 1, 0, 1,  1);  // 1|0=1
        check(0, 0, 1, 1,  1);  // 0|1=1
        check(0, 1, 1, 1,  1);  // 1|1=1

        // CRITICAL: b and sel fixed, only c changes
        // If c not in sensitivity list -> output stuck, won't update
        a=0; sel=1; b=0; c=0; #20;   // expect 0
        if (out!==0) begin $display("FAIL: b=0 c=0 sel=1 -> exp 0, got %0d",out); fail=fail+1; end
        c=1; #20;                      // c changes, output MUST update
        if (out!==1) begin $display("FAIL SENSITIVITY: c changed 0->1 but out still %0d (exp 1)",out); fail=fail+1; end
        c=0; #20;
        if (out!==0) begin $display("FAIL SENSITIVITY: c changed 1->0 but out still %0d (exp 0)",out); fail=fail+1; end

        // ── sel switching ─────────────────────────────────────────────────
        check(1, 1, 0, 0,  1);  // sel=0: 1&1=1
        check(1, 1, 0, 1,  1);  // sel=1: 1|0=1
        check(1, 0, 0, 0,  0);  // sel=0: 1&0=0
        check(1, 0, 1, 1,  1);  // sel=1: 0|1=1

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
