module counter_4bit_tb;
    reg clk, rst;
    wire [3:0] count;
    integer fail = 0;
    integer i;

    counter_4bit uut (.clk(clk), .rst(rst), .count(count));

    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        // Reset test
        rst = 1;
        @(posedge clk); #1;
        if (count !== 4'd0) begin
            $display("FAIL: reset did not zero count. got %0d", count);
            fail = fail + 1;
        end else $display("PASS reset");

        // Count 0..15 then rollover
        rst = 0;
        for (i = 0; i < 16; i = i+1) begin
            @(posedge clk); #1;
            if (count !== i+1 && !(i==15 && count==0)) begin
                // Allow rollover: after 15 expect 0
                if (i == 15) begin
                    if (count !== 4'd0) begin
                        $display("FAIL rollover: expected 0 got %0d", count);
                        fail = fail + 1;
                    end else $display("PASS rollover");
                end else begin
                    $display("FAIL count step %0d: expected %0d got %0d", i, i+1, count);
                    fail = fail + 1;
                end
            end else begin
                if (i != 15) $display("PASS count=%0d", count);
            end
        end

        // Reset mid-count
        @(posedge clk); #1; // count = 1
        @(posedge clk); #1; // count = 2
        rst = 1;
        @(posedge clk); #1;
        if (count !== 4'd0) begin
            $display("FAIL mid-reset: got %0d", count);
            fail = fail + 1;
        end else $display("PASS mid-reset");

        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
