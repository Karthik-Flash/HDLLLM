// L4 Processor submodule: CPU ALU
// Module: simple_cpu_alu
// Ports: input [3:0] A, B, input [1:0] op, output [3:0] result, output zero
// op: 00=ADD 01=SUB 10=AND 11=OR
module simple_cpu_alu_tb;
    reg  [3:0] A, B;
    reg  [1:0] op;
    wire [3:0] result;
    wire zero;
    integer fail = 0;

    simple_cpu_alu uut (.A(A), .B(B), .op(op), .result(result), .zero(zero));

    task check;
        input [3:0] exp_r;
        input exp_z;
        input [31:0] tid;
        begin
            #1;
            if (result !== exp_r || zero !== exp_z) begin
                $display("FAIL test%0d: A=%0d B=%0d op=%b | got r=%0d z=%b | exp r=%0d z=%b",
                    tid, A, B, op, result, zero, exp_r, exp_z);
                fail = fail + 1;
            end else $display("PASS test%0d", tid);
        end
    endtask

    initial begin
        A=4'd5;  B=4'd3;  op=2'b00; check(4'd8,  0, 1);   // ADD
        A=4'd0;  B=4'd0;  op=2'b00; check(4'd0,  1, 2);   // ADD zero
        A=4'd15; B=4'd1;  op=2'b00; check(4'd0,  1, 3);   // ADD overflow wraps 4-bit
        A=4'd7;  B=4'd3;  op=2'b01; check(4'd4,  0, 4);   // SUB
        A=4'd5;  B=4'd5;  op=2'b01; check(4'd0,  1, 5);   // SUB = zero
        A=4'hF;  B=4'hA;  op=2'b10; check(4'hA,  0, 6);   // AND
        A=4'hA;  B=4'h5;  op=2'b10; check(4'h0,  1, 7);   // AND = zero
        A=4'hA;  B=4'h5;  op=2'b11; check(4'hF,  0, 8);   // OR
        A=4'h0;  B=4'h0;  op=2'b11; check(4'h0,  1, 9);   // OR zero
        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
