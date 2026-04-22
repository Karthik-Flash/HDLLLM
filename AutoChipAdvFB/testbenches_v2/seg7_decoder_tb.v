// seg7_decoder_tb.v
// 4-bit BCD input -> 7-segment output (active high)
// seg[6:0] = {g, f, e, d, c, b, a}
// Tests 0-9 (defined by spec) AND 10-15 (undefined in spec -> expects 7'b0000000)
// LLM without default: latch holds last seg value -> FAIL on inputs 10-15
// With Yosys "Inferred latch" feedback: LLM adds default -> PASS
module seg7_decoder_tb;
    reg  [3:0] bcd;
    wire [6:0] seg;

    seg7_decoder dut(.bcd(bcd), .seg(seg));

    integer fail = 0;

    task check;
        input [3:0] in;
        input [6:0] exp;
        begin
            bcd = in; #10;
            if (seg !== exp) begin
                $display("FAIL bcd=%0d: got seg=%b, exp=%b", in, seg, exp);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // ── Defined digits 0-9 ──────────────────────────────────────────
        check(4'd0,  7'b0111111);  // a,b,c,d,e,f on
        check(4'd1,  7'b0000110);  // b,c on
        check(4'd2,  7'b1011011);  // a,b,d,e,g on
        check(4'd3,  7'b1001111);  // a,b,c,d,g on
        check(4'd4,  7'b1100110);  // b,c,f,g on
        check(4'd5,  7'b1101101);  // a,c,d,f,g on
        check(4'd6,  7'b1111101);  // a,c,d,e,f,g on
        check(4'd7,  7'b0000111);  // a,b,c on
        check(4'd8,  7'b1111111);  // all on
        check(4'd9,  7'b1101111);  // a,b,c,d,f,g on

        // ── Undefined inputs 10-15: should output blank (7'b0000000) ─────
        // Without a default in the case statement, a latch is inferred and
        // the output holds the previous value (9's encoding 7'b1101111)
        // instead of going to 0.  This is the failure Yosys diagnoses.
        check(4'd10, 7'b0000000);
        check(4'd11, 7'b0000000);
        check(4'd12, 7'b0000000);
        check(4'd13, 7'b0000000);
        check(4'd14, 7'b0000000);
        check(4'd15, 7'b0000000);

        // ── Transition back to valid: verify latch didn't corrupt state ──
        check(4'd0,  7'b0111111);
        check(4'd5,  7'b1101101);

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
