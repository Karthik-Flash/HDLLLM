// parity_checker_8bit_tb.v
// mode=0: even parity -> parity_ok=1 when count of 1s is even
// mode=1: odd  parity -> parity_ok=1 when count of 1s is odd
module parity_checker_8bit_tb;
    reg [7:0] data;
    reg       mode;
    wire      parity_ok;

    parity_checker_8bit dut(.data(data),.mode(mode),.parity_ok(parity_ok));

    integer fail = 0;

    task check;
        input [7:0] edata;
        input       emode;
        input       epok;
        begin
            data=edata; mode=emode; #10;
            if (parity_ok !== epok) begin
                $display("FAIL: data=%b mode=%0d -> got parity_ok=%0d, exp %0d",
                          edata, emode, parity_ok, epok);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // Even parity mode (mode=0): parity_ok=1 when #ones is EVEN
        check(8'b0000_0000, 0, 1); // 0 ones -> even -> ok
        check(8'b0000_0001, 0, 0); // 1 one  -> odd  -> not ok
        check(8'b0000_0011, 0, 1); // 2 ones -> even -> ok
        check(8'b0000_0111, 0, 0); // 3 ones -> odd  -> not ok
        check(8'b0000_1111, 0, 1); // 4 ones -> even -> ok
        check(8'b1111_1111, 0, 1); // 8 ones -> even -> ok
        check(8'b1010_1010, 0, 1); // 4 ones -> even -> ok
        check(8'b1000_0000, 0, 0); // 1 one  -> odd  -> not ok
        check(8'b0111_1111, 0, 0); // 7 ones -> odd  -> not ok
        check(8'b1010_0101, 0, 1); // 4 ones (7,5,2,0) -> even -> ok

        // Odd parity mode (mode=1): parity_ok=1 when #ones is ODD
        check(8'b0000_0000, 1, 0); // 0 ones -> even -> not ok
        check(8'b0000_0001, 1, 1); // 1 one  -> odd  -> ok
        check(8'b0000_0011, 1, 0); // 2 ones -> even -> not ok
        check(8'b0000_0111, 1, 1); // 3 ones -> odd  -> ok
        check(8'b0000_1111, 1, 0); // 4 ones -> even -> not ok
        check(8'b1111_1111, 1, 0); // 8 ones -> even -> not ok
        check(8'b1000_0000, 1, 1); // 1 one  -> odd  -> ok
        check(8'b1000_0011, 1, 1); // 3 ones -> odd  -> ok
        check(8'b0111_1111, 1, 1); // 7 ones -> odd  -> ok
        check(8'b1010_0101, 1, 0); // 4 ones -> even -> not ok

        // Mode switch on same data
        check(8'b1100_0011, 0, 1); // 4 ones -> even -> ok  (mode=0)
        check(8'b1100_0011, 1, 0); // 4 ones -> even -> not ok (mode=1)
        check(8'b1100_0001, 0, 0); // 3 ones -> odd  -> not ok (mode=0)
        check(8'b1100_0001, 1, 1); // 3 ones -> odd  -> ok  (mode=1)

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
