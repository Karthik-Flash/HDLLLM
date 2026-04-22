module uart_tx (
    input clk,
    input rst,
    input start,
    input [7:0] data_in,
    output reg tx_out,
    output reg busy,
    output reg done
);

parameter BAUD_DIV = 104;

// FSM states
parameter IDLE  = 3'd0;
parameter START = 3'd1;
parameter DATA  = 3'd2;
parameter STOP  = 3'd3;
parameter DONE  = 3'd4;

// Internal registers
reg [2:0] state;
reg [7:0] shift_reg;
reg [7:0] baud_cnt;
reg [3:0] bit_cnt;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state     <= IDLE;
        tx_out    <= 1'b1;
        busy      <= 1'b0;
        done      <= 1'b0;
        shift_reg <= 8'd0;
        baud_cnt  <= 8'd0;
        bit_cnt   <= 4'd0;
    end else begin
        // Default assignment for done to create a one-cycle pulse
        done <= 1'b0;

        case (state)
            IDLE: begin
                tx_out <= 1'b1;
                busy   <= 1'b0;
                // done is already 0
                if (start) begin
                    state     <= START;
                    shift_reg <= data_in;
                    baud_cnt  <= 8'd0;
                    bit_cnt   <= 4'd0;
                end else begin
                    state <= IDLE;
                end
            end

            START: begin
                tx_out <= 1'b0;
                busy   <= 1'b1;
                if (baud_cnt == BAUD_DIV - 1) begin
                    state    <= DATA;
                    baud_cnt <= 8'd0;
                end else begin
                    state    <= START;
                    baud_cnt <= baud_cnt + 1;
                end
            end

            DATA: begin
                busy   <= 1'b1;
                tx_out <= shift_reg[0];
                if (baud_cnt == BAUD_DIV - 1) begin
                    baud_cnt <= 8'd0;
                    shift_reg <= {1'b0, shift_reg[7:1]};
                    bit_cnt <= bit_cnt + 1;
                    if (bit_cnt == 4'd7) begin
                        state <= STOP;
                    end else begin
                        state <= DATA;
                    end
                end else begin
                    state    <= DATA;
                    baud_cnt <= baud_cnt + 1;
                end
            end

            STOP: begin
                tx_out <= 1'b1;
                busy   <= 1'b1;
                if (baud_cnt == BAUD_DIV - 1) begin
                    state    <= DONE;
                    baud_cnt <= 8'd0;
                end else begin
                    state    <= STOP;
                    baud_cnt <= baud_cnt + 1;
                end
            end

            DONE: begin
                done   <= 1'b1;
                busy   <= 1'b0;
                tx_out <= 1'b1;
                state  <= IDLE;
            end

            default: begin
                state <= IDLE;
            end
        endcase
    end
end

endmodule