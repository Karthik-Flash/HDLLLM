// FSM Mealy detector for sequence 1011
// Module: fsm_seq_detector
// Ports: input clk, rst, in; output detected
module fsm_seq_detector_tb;
    reg clk, rst, in;
    wire detected;
    integer fail = 0;

    fsm_seq_detector uut (.clk(clk), .rst(rst), .in(in), .detected(detected));

    initial clk = 0;
    always #5 clk = ~clk;

    task send_bit;
        input b;
        input exp_det;
        input [31:0] tid;
        begin
            in = b;
            @(posedge clk); #1;
            if (detected !== exp_det) begin
                $display("FAIL test%0d: in=%b | got detected=%b | expected=%b", tid, b, detected, exp_det);
                fail = fail + 1;
            end else $display("PASS test%0d (in=%b detected=%b)", tid, b, detected);
        end
    endtask

    initial begin
        rst=1; in=0; @(posedge clk); #1; rst=0;

        // Sequence: 1 0 1 1 -> detect on last 1
        send_bit(1, 0, 1);
        send_bit(0, 0, 2);
        send_bit(1, 0, 3);
        send_bit(1, 1, 4);  // DETECTED

        // No detection on: 1 0 1 0
        send_bit(1, 0, 5);
        send_bit(0, 0, 6);
        send_bit(1, 0, 7);
        send_bit(0, 0, 8);  // no detect

        // Overlapping: 1 0 1 1 0 1 1 -> second detect
        rst=1; @(posedge clk); #1; rst=0;
        send_bit(1, 0, 9);
        send_bit(0, 0, 10);
        send_bit(1, 0, 11);
        send_bit(1, 1, 12); // first detect
        send_bit(0, 0, 13);
        send_bit(1, 0, 14);
        send_bit(1, 1, 15); // second detect

        // All zeros -> never detect
        rst=1; @(posedge clk); #1; rst=0;
        send_bit(0, 0, 16);
        send_bit(0, 0, 17);
        send_bit(0, 0, 18);
        send_bit(0, 0, 19);

        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
