module register_file_4x8_tb;
    reg clk,we; reg [1:0] waddr,raddr1,raddr2; reg [7:0] wdata;
    wire [7:0] rdata1,rdata2; integer fail=0;
    register_file_4x8 uut(.clk(clk),.we(we),.waddr(waddr),.raddr1(raddr1),.raddr2(raddr2),.wdata(wdata),.rdata1(rdata1),.rdata2(rdata2));
    initial clk=0; always #5 clk=~clk;
    initial begin
        we=1; waddr=2'd0; wdata=8'hAA; @(posedge clk); #1;
        we=1; waddr=2'd1; wdata=8'hBB; @(posedge clk); #1;
        we=1; waddr=2'd2; wdata=8'hCC; @(posedge clk); #1;
        we=1; waddr=2'd3; wdata=8'hDD; @(posedge clk); #1;
        we=0; raddr1=2'd0; raddr2=2'd3; #1;
        if(rdata1!==8'hAA) begin $display("FAIL r0"); fail=fail+1; end else $display("PASS r0");
        if(rdata2!==8'hDD) begin $display("FAIL r3"); fail=fail+1; end else $display("PASS r3");
        raddr1=2'd1; raddr2=2'd2; #1;
        if(rdata1!==8'hBB) begin $display("FAIL r1"); fail=fail+1; end else $display("PASS r1");
        if(rdata2!==8'hCC) begin $display("FAIL r2"); fail=fail+1; end else $display("PASS r2");
        if(fail==0) $display("ALL TESTS PASSED"); else $display("%0d TEST(S) FAILED",fail);
        $finish;
    end
endmodule
