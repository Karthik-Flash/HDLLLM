// uart_rx_tb.v  —  control module (pure FSM logic, Yosys/Verilator don't help)
// Simple UART RX: 8-N-1, CLKS_PER_BIT=4 for fast simulation
// FSM: IDLE -> START (detect low) -> DATA (shift 8 bits) -> STOP -> IDLE
// data_valid pulses for 1 cycle when byte is received
`timescale 1ns/1ps
module uart_rx_tb;

    parameter CLKS_PER_BIT = 4;

    reg        clk, rst, rx;
    wire [7:0] rx_data;
    wire       data_valid;

    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) dut(
        .clk(clk), .rst(rst), .rx(rx),
        .rx_data(rx_data), .data_valid(data_valid)
    );

    always #5 clk = ~clk;

    integer fail = 0;
    integer i;

    // Send one UART byte: start bit + 8 data bits (LSB first) + stop bit
    task send_byte;
        input [7:0] byte_val;
        integer bit_idx;
        begin
            // Start bit (low)
            rx = 0;
            repeat(CLKS_PER_BIT) @(posedge clk);

            // Data bits LSB first
            for (bit_idx = 0; bit_idx < 8; bit_idx = bit_idx + 1) begin
                rx = byte_val[bit_idx];
                repeat(CLKS_PER_BIT) @(posedge clk);
            end

            // Stop bit (high)
            rx = 1;
            repeat(CLKS_PER_BIT) @(posedge clk);
        end
    endtask

    // Wait for data_valid then check received byte
    task check_byte;
        input [7:0] expected;
        integer timeout;
        begin
            timeout = 0;
            while (data_valid === 0 && timeout < 200) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
            end
            if (timeout >= 200) begin
                $display("FAIL: data_valid never asserted (timeout)");
                fail = fail + 1;
            end else if (rx_data !== expected) begin
                $display("FAIL: got rx_data=8'h%h, exp=8'h%h", rx_data, expected);
                fail = fail + 1;
            end
        end
    endtask

    initial begin
        clk = 0; rst = 1; rx = 1;  // idle line high
        repeat(4) @(posedge clk);
        rst = 0;

        // Test 1: send 0x55 (0101_0101)
        fork
            send_byte(8'h55);
            check_byte(8'h55);
        join

        repeat(4) @(posedge clk);

        // Test 2: send 0xA3
        fork
            send_byte(8'hA3);
            check_byte(8'hA3);
        join

        repeat(4) @(posedge clk);

        // Test 3: send 0x00
        fork
            send_byte(8'h00);
            check_byte(8'h00);
        join

        repeat(4) @(posedge clk);

        // Test 4: send 0xFF
        fork
            send_byte(8'hFF);
            check_byte(8'hFF);
        join

        repeat(4) @(posedge clk);

        // Test 5: back-to-back bytes
        fork
            begin
                send_byte(8'h12);
                send_byte(8'h34);
            end
            begin
                check_byte(8'h12);
                check_byte(8'h34);
            end
        join

        if (fail == 0)
            $display("ALL TESTS PASSED");
        else
            $display("FAIL: %0d test(s) failed", fail);

        $finish;
    end
endmodule
