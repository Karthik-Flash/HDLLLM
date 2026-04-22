// 8-bit ALU testbench
// Module: alu_8bit
// Ports: input [7:0] A, B, input [2:0] op, output [7:0] result, output zero
// op: 000=ADD 001=SUB 010=AND 011=OR 100=XOR 101=NOT_A 110=SHL 111=SHR
module alu_8bit_tb;
    reg  [7:0] A, B;
    reg  [2:0] op;
    wire [7:0] result;
    wire zero;
    integer fail = 0;

    alu_8bit uut (.A(A), .B(B), .op(op), .result(result), .zero(zero));

    task check;
        input [7:0] exp_result;
        input exp_zero;
        input [31:0] tid;
        begin
            #2;
            if (result !== exp_result || zero !== exp_zero) begin
                $display("FAIL test%0d: A=%0d B=%0d op=%b | got result=%0d zero=%b | exp result=%0d zero=%b",
                    tid, A, B, op, result, zero, exp_result, exp_zero);
                fail = fail + 1;
            end else
                $display("PASS test%0d", tid);
        end
    endtask

    initial begin
        // ADD
        A=8'd10; B=8'd5;  op=3'b000; check(8'd15, 0, 1);
        A=8'd0;  B=8'd0;  op=3'b000; check(8'd0,  1, 2);
        A=8'd255;B=8'd1;  op=3'b000; check(8'd0,  1, 3);  // overflow wraps
        // SUB
        A=8'd10; B=8'd3;  op=3'b001; check(8'd7,  0, 4);
        A=8'd5;  B=8'd5;  op=3'b001; check(8'd0,  1, 5);
        // AND
        A=8'hFF; B=8'h0F; op=3'b010; check(8'h0F, 0, 6);
        A=8'hAA; B=8'h55; op=3'b010; check(8'h00, 1, 7);
        // OR
        A=8'hA0; B=8'h05; op=3'b011; check(8'hA5, 0, 8);
        // XOR
        A=8'hFF; B=8'hFF; op=3'b100; check(8'h00, 1, 9);
        A=8'hAA; B=8'h55; op=3'b100; check(8'hFF, 0, 10);
        // NOT A
        A=8'h00; B=8'h00; op=3'b101; check(8'hFF, 0, 11);
        A=8'hFF; B=8'h00; op=3'b101; check(8'h00, 1, 12);
        // SHL (logical left shift A by 1)
        A=8'b00001111; B=8'd0; op=3'b110; check(8'b00011110, 0, 13);
        A=8'b10000000; B=8'd0; op=3'b110; check(8'b00000000, 1, 14);
        // SHR (logical right shift A by 1)
        A=8'b11110000; B=8'd0; op=3'b111; check(8'b01111000, 0, 15);
        A=8'b00000001; B=8'd0; op=3'b111; check(8'b00000000, 1, 16);

        if (fail == 0) $display("ALL TESTS PASSED");
        else $display("%0d TEST(S) FAILED", fail);
        $finish;
    end
endmodule
