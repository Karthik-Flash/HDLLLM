module simple_cpu_regfile_tb;
    reg clk,rst,we; reg [1:0] waddr,raddr1,raddr2; reg [3:0] wdata;
    wire [3:0] rdata1,rdata2; integer fail=0;
    simple_cpu_regfile uut(.clk(clk),.rst(rst),.we(we),.waddr(waddr),.raddr1(raddr1),.raddr2(raddr2),.wdata(wdata),.rdata1(rdata1),.rdata2(rdata2));
    initial clk=0; always #5 clk=~clk;
    initial begin
        rst=1; we=0; @(posedge clk); #1; rst=0;
        we=1; waddr=2'd0; wdata=4'd5; @(posedge clk); #1;
        we=1; waddr=2'd1; wdata=4'd3; @(posedge clk); #1;
        we=1; waddr=2'd2; wdata=4'd7; @(posedge clk); #1;
        we=1; waddr=2'd3; wdata=4'd1; @(posedge clk); #1;
        we=0; raddr1=2'd0; raddr2=2'd1; #1;
        if(rdata1!==4'd5) begin $display("FAIL r0"); fail=fail+1; end else $display("PASS r0");
        if(rdata2!==4'd3) begin $display("FAIL r1"); fail=fail+1; end else $display("PASS r1");
        raddr1=2'd2; raddr2=2'd3; #1;
        if(rdata1!==4'd7) begin $display("FAIL r2"); fail=fail+1; end else $display("PASS r2");
        if(rdata2!==4'd1) begin $display("FAIL r3"); fail=fail+1; end else $display("PASS r3");
        rst=1; @(posedge clk); #1; raddr1=2'd0; #1;
        if(rdata1!==4'd0) begin $display("FAIL rst_clear"); fail=fail+1; end else $display("PASS rst_clear");
        if(fail==0) $display("ALL TESTS PASSED"); else $display("%0d TEST(S) FAILED",fail);
        $finish;
    end
endmodule
