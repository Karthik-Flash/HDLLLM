// alu_ops_tb.v
// 3-bit opcode ALU:
//   000=ADD, 001=SUB, 010=AND, 011=OR, 100=XOR
//   101,110,111 = undefined (spec silent) -> result=0, carry_out=0, zero=1
// LLM without default: case covers 5 opcodes, latch holds last result for 101-111
// Yosys flags "Inferred latch for signal \result" -> LLM adds default -> PASS
module alu_ops_tb;
    reg  [7:0] a, b;
    reg  [2:0] opcode;
    wire [7:0] result;
    wire       carry_out, zero;

    alu_ops dut(.a(a),.b(b),.opcode(opcode),
                .result(result),.carry_out(carry_out),.zero(zero));

    integer fail = 0;

    task check;
        input [7:0] ta, tb;
        input [2:0] top;
        input [7:0] eres;
        input       eco, ezo;
        begin
            a=ta; b=tb; opcode=top; #10;
            if (result!==eres || carry_out!==eco || zero!==ezo) begin
                $display("FAIL op=%b a=%0d b=%0d: got result=%0d co=%0d z=%0d | exp result=%0d co=%0d z=%0d",
                         top,ta,tb,result,carry_out,zero,eres,eco,ezo);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        // ── ADD (000) ───────────────────────────────────────────────────
        check(8'd10,  8'd5,  3'b000, 8'd15,  1'b0, 1'b0);
        check(8'd0,   8'd0,  3'b000, 8'd0,   1'b0, 1'b1);
        check(8'd200, 8'd100,3'b000, 8'd44,  1'b1, 1'b0);  // overflow: 300->44, carry=1
        check(8'd255, 8'd1,  3'b000, 8'd0,   1'b1, 1'b1);  // carry + zero

        // ── SUB (001) ───────────────────────────────────────────────────
        check(8'd10,  8'd3,  3'b001, 8'd7,   1'b0, 1'b0);
        check(8'd5,   8'd5,  3'b001, 8'd0,   1'b0, 1'b1);  // zero
        check(8'd3,   8'd10, 3'b001, 8'd249, 1'b1, 1'b0);  // borrow

        // ── AND (010) ───────────────────────────────────────────────────
        check(8'hF0,  8'hAA, 3'b010, 8'hA0,  1'b0, 1'b0);
        check(8'hFF,  8'h00, 3'b010, 8'h00,  1'b0, 1'b1);

        // ── OR (011) ────────────────────────────────────────────────────
        check(8'hF0,  8'h0F, 3'b011, 8'hFF,  1'b0, 1'b0);
        check(8'h00,  8'h00, 3'b011, 8'h00,  1'b0, 1'b1);

        // ── XOR (100) ───────────────────────────────────────────────────
        check(8'hFF,  8'hFF, 3'b100, 8'h00,  1'b0, 1'b1);
        check(8'hAA,  8'h55, 3'b100, 8'hFF,  1'b0, 1'b0);

        // ── Undefined opcodes 101,110,111: must output 0,0,1 ─────────────
        // Without default: latch holds last XOR result (8'hFF) -> FAIL
        // Yosys: "Inferred latch for signal \result" -> LLM adds default -> PASS
        check(8'd99,  8'd33, 3'b101, 8'd0, 1'b0, 1'b1);
        check(8'd42,  8'd42, 3'b110, 8'd0, 1'b0, 1'b1);
        check(8'd1,   8'd1,  3'b111, 8'd0, 1'b0, 1'b1);

        // ── Return to defined op: verify no corruption ───────────────────
        check(8'd2,   8'd3,  3'b010, 8'd2, 1'b0, 1'b0);  // AND

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
