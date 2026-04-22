module shift_register_8bit_tb;
    reg clk, rst, sin;
    wire sout;
    wire [7:0] data;
    integer fail = 0;
    shift_register_8bit uut(.clk(clk),.rst(rst),.sin(sin),.sout(sout),.data(data));
    initial clk=0;
    always #5 clk=~clk;
    initial begin
        rst=1; sin=0; @(posedge clk); #1;
        if(data!==8'h00) begin $display("FAIL reset"); fail=fail+1; end
        else $display("PASS reset");
        rst=0;
        sin=1; @(posedge clk); #1; if(data!==8'h01) begin $display("FAIL shift1"); fail=fail+1; end else $display("PASS shift1");
        sin=0; @(posedge clk); #1; if(data!==8'h02) begin $display("FAIL shift2"); fail=fail+1; end else $display("PASS shift2");
        sin=1; @(posedge clk); #1; if(data!==8'h05) begin $display("FAIL shift3"); fail=fail+1; end else $display("PASS shift3");
        sin=1; @(posedge clk); #1; if(data!==8'h0B) begin $display("FAIL shift4"); fail=fail+1; end else $display("PASS shift4");
        sin=0; @(posedge clk); #1; if(data!==8'h16) begin $display("FAIL shift5"); fail=fail+1; end else $display("PASS shift5");
        sin=1; @(posedge clk); #1; if(data!==8'h2D) begin $display("FAIL shift6"); fail=fail+1; end else $display("PASS shift6");
        sin=1; @(posedge clk); #1; if(data!==8'h5B) begin $display("FAIL shift7"); fail=fail+1; end else $display("PASS shift7");
        sin=1; @(posedge clk); #1; if(data!==8'hB7) begin $display("FAIL shift8"); fail=fail+1; end else $display("PASS shift8");
        if(sout!==1'b1) begin $display("FAIL sout"); fail=fail+1; end else $display("PASS sout");
        if(fail==0) $display("ALL TESTS PASSED"); else $display("%0d TEST(S) FAILED",fail);
        $finish;
    end
endmodule
