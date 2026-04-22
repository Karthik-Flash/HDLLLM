`timescale 1ns/1ps
// 2-stage pipeline: product valid 2 posedges after inputs presented.
// Stage 1: a_r <= a; b_r <= b
// Stage 2: product <= a_r * b_r
// A 1-stage (combinational) implementation will FAIL because output appears at cycle 1, not 2.
module pipeline_mult_4x4_tb;
  reg        clk = 0;
  reg  [3:0] a, b;
  wire [7:0] product;
  integer fail = 0;

  pipeline_mult_4x4 uut (.clk(clk), .a(a), .b(b), .product(product));

  always #5 clk = ~clk;

  task tick; begin @(posedge clk); #1; end endtask

  initial begin
    a = 4'd0; b = 4'd0;
    tick; tick; // pipeline flush / settle

    // ── Test 1: apply (3,4) at cycle 0; expect product=12 at cycle 2 ─────
    a = 4'd3; b = 4'd4;  // input presented at posedge 0
    tick; // cycle 1: a_r=3, b_r=4 registered. product is NOT yet 12.
    // At cycle 1, product should NOT be 12 (it would only be if pipeline is 1-stage).
    // We check AFTER cycle 2.
    tick; // cycle 2: product = a_r*b_r = 3*4 = 12
    if (product !== 8'd12) begin
      $display("FAIL [3*4]: expected product=12 after 2 cycles, got %0d", product); fail = fail + 1;
    end

    // ── Test 2: change input to (5,6) at cycle 2; expect 30 at cycle 4 ───
    a = 4'd5; b = 4'd6;  // cycle 2 (already ticked above)
    tick; // cycle 3: a_r=5, b_r=6
    // At this point (cycle 3), the OLD result (3*4=12) should still be in product
    // (from (3,4) which was latched at cycle 1 into stage 2 at cycle 2).
    // After tick above (cycle 3): product becomes (0,0) * something from initial state.
    // Actually: what's in stage 2 at cycle 3? It holds a_r,b_r from cycle 2 (which was 5,6→a_r).
    // Stage 2 at cycle 3: product = a_r(cycle2) * b_r(cycle2) = 3*4 from (3,4) input.
    // Wait — let me re-trace:
    // Cycle 0 tick: a=3,b=4 → a_r=3, b_r=4 registered (stage1).  product = old (don't care).
    // Cycle 1 tick: a=3,b=4 → stage1: a_r=3,b_r=4 again. Stage2: product = 3*4=12.
    // ABOVE tick was cycle 1. product=12 checked. ✓
    // Cycle 2 (second tick above): a changed to 5,b=6 BEFORE tick.
    //   stage1: a_r=5, b_r=6.  stage2: product = old_a_r*old_b_r = 3*4=12.
    //   We check product===12 after this tick. (Already checked above.)
    // Cycle 3 (third tick): a=5,b=6 (no change).
    //   stage1: a_r=5, b_r=6.  stage2: product = 5*6=30. ← check here.
    if (product !== 8'd30) begin
      $display("FAIL [5*6]: expected product=30 at cycle 3, got %0d", product); fail = fail + 1;
    end

    // ── Test 3: back-to-back inputs, verify each result appears 2 cycles later ──
    // Apply (2,3) → expect 6 two cycles later
    a = 4'd2; b = 4'd3; tick;  // cycle 4: stage1 latches 2,3
    a = 4'd7; b = 4'd7; tick;  // cycle 5: stage1 latches 7,7. stage2: product=2*3=6
    if (product !== 8'd6) begin
      $display("FAIL [2*3]: expected 6 at cycle 5, got %0d", product); fail = fail + 1;
    end
    a = 4'd1; b = 4'd1; tick;  // cycle 6: stage2: product=7*7=49
    if (product !== 8'd49) begin
      $display("FAIL [7*7]: expected 49 at cycle 6, got %0d", product); fail = fail + 1;
    end
    tick;                       // cycle 7: product=1*1=1
    if (product !== 8'd1) begin
      $display("FAIL [1*1]: expected 1 at cycle 7, got %0d", product); fail = fail + 1;
    end

    // ── Test 4: max input 15*15=225 ──────────────────────────────────────
    a = 4'd15; b = 4'd15; tick; // stage1: 15,15
    a = 4'd0;  b = 4'd0;  tick; // stage2: 15*15=225
    if (product !== 8'd225) begin
      $display("FAIL [15*15]: expected 225, got %0d", product); fail = fail + 1;
    end

    if (fail == 0) $display("ALL TESTS PASSED");
    $finish;
  end
endmodule
