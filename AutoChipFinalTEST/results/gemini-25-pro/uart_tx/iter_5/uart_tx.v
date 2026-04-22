module uart_tx #(
    parameter BAUD_DIV = 104
) (
    input clk,
    input rst,
    input start,
    input [7:0] data_in,

    output reg tx_out,
    output reg busy,
    output reg done
);

// FSM States
localparam [2:0]
    IDLE  = 3'd0,
    START = 3'd1,
    DATA  = 3'd2,
    STOP  = 3'd3,
    DONE  = 3'd4;

// Internal Registers
reg [2:0] state;
reg [7:0] shift_reg;
reg [7:0] baud_cnt; // Declared as [7:0] as per requirement
reg [3:0] bit_cnt;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state <= IDLE;
        tx_out <= 1'b1;
        busy <= 1'b0;
        done <= 1'b0;
        shift_reg <= 8'h00;
        baud_cnt <= BAUD_DIV - 1; // Initialize baud_cnt for countdown from BAUD_DIV-1 to 0
        bit_cnt <= 4'h0;
    end else begin
        // Default assignments for next cycle, will be overridden by state logic
        reg [2:0] next_state = state;
        reg [7:0] next_shift_reg = shift_reg;
        reg [7:0] next_baud_cnt = baud_cnt;
        reg [3:0] next_bit_cnt = bit_cnt;
        reg next_tx_out = tx_out;
        reg next_busy = busy;
        reg next_done = 1'b0; // 'done' is only high for one cycle in the DONE state

        case (state)
            IDLE: begin
                next_tx_out = 1'b1; // Default idle state is high
                next_busy = 1'b0;   // Not busy in idle
                next_baud_cnt = BAUD_DIV - 1; // Reset baud_cnt for next transmission
                next_bit_cnt = 4'h0;   // Reset bit_cnt
                if (start) begin
                    next_state = START;
                    next_shift_reg = data_in; // Latch data_in
                    next_tx_out = 1'b0; // Assert start bit immediately on transition
                    next_busy = 1'b1;   // Assert busy immediately on transition
                end
            end

            START: begin
                next_tx_out = 1'b0; // Keep start bit low
                next_busy = 1'b1;   // Keep busy asserted
                if (baud_cnt == 0) begin // Last cycle of BAUD_DIV period
                    next_state = DATA;
                    next_baud_cnt = BAUD_DIV - 1; // Reset baud_cnt for next bit
                    next_bit_cnt = 4'h0;   // Initialize bit_cnt for data bits (0 to 7)
                    next_tx_out = shift_reg[0]; // Set first data bit for the next state
                end else begin
                    next_baud_cnt = baud_cnt - 1;
                end
            end

            DATA: begin
                next_busy = 1'b1; // Keep busy asserted
                // next_tx_out holds its current value for the duration of the bit
                if (baud_cnt == 0) begin // Last cycle of BAUD_DIV period
                    next_baud_cnt = BAUD_DIV - 1; // Reset baud_cnt for next bit
                    next_shift_reg = shift_reg >> 1; // Shift data for next bit
                    if (bit_cnt == 7) begin // After 8 bits (0 to 7)
                        next_state = STOP;
                        next_bit_cnt = 4'h0; // Reset bit_cnt for next frame
                        next_tx_out = 1'b1; // Set stop bit for the next state
                    end else begin
                        next_bit_cnt = bit_cnt + 1;
                        // Set next data bit for the next state.
                        // (shift_reg >> 1)[0] correctly gets the LSB of the *next* data byte.
                        next_tx_out = (shift_reg >> 1)[0];
                    end
                end else begin
                    next_baud_cnt = baud_cnt - 1;
                end
            end

            STOP: begin
                next_tx_out = 1'b1; // Keep stop bit high
                next_busy = 1'b1;   // Keep busy asserted
                if (baud_cnt == 0) begin // Last cycle of BAUD_DIV period
                    next_state = DONE;
                    next_baud_cnt = BAUD_DIV - 1; // Reset baud_cnt
                end else begin
                    next_baud_cnt = baud_cnt - 1;
                end
            end

            DONE: begin
                next_tx_out = 1'b1; // Keep high
                next_busy = 1'b0;
                next_done = 1'b1; // Assert done for one cycle
                next_state = IDLE; // Go back to IDLE
            end

            default: begin // Should not happen, but good for completeness
                next_state = IDLE;
                next_tx_out = 1'b1;
                next_busy = 1'b0;
                next_done = 1'b0;
                next_shift_reg = 8'h00;
                next_baud_cnt = BAUD_DIV - 1;
                next_bit_cnt = 4'h0;
            end
        endcase

        // Apply all non-blocking assignments at the end of the always block
        state <= next_state;
        shift_reg <= next_shift_reg;
        baud_cnt <= next_baud_cnt;
        bit_cnt <= next_bit_cnt;
        tx_out <= next_tx_out;
        busy <= next_busy;
        done <= next_done;
    end
end

endmodule