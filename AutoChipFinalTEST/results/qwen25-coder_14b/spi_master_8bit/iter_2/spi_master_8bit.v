module spi_master_8bit (
    input clk,
    input rst,
    input start,
    input [7:0] mosi_data,
    input miso,
    output reg sclk,
    output reg cs_n,
    output reg mosi,
    output reg done,
    output reg [7:0] miso_capture
);

parameter CLK_DIV = 4;

reg [1:0] state;
reg [7:0] shift_out, shift_in;
reg [3:0] clk_cnt, bit_cnt;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state <= 2'b00; // IDLE
        cs_n <= 1'b1;
        sclk <= 1'b0;
        done <= 1'b0;
        miso_capture <= 8'b0;
    end else begin
        case (state)
            2'b00: begin // IDLE
                if (start) begin
                    cs_n <= 1'b0;
                    shift_out <= mosi_data;
                    bit_cnt <= 4'd0;
                    clk_cnt <= 4'd0;
                    state <= 2'b01; // ACTIVE
                end else begin
                    cs_n <= 1'b1;
                    sclk <= 1'b0;
                    done <= 1'b0;
                end
            end
            2'b01: begin // ACTIVE
                if (clk_cnt < CLK_DIV) begin
                    sclk <= 1'b0;
                    mosi <= shift_out[7];
                end else if (clk_cnt == CLK_DIV - 1) begin
                    sclk <= 1'b1; // Rising edge
                end else if (clk_cnt >= CLK_DIV && clk_cnt < 2 * CLK_DIV - 1) begin
                    sclk <= 1'b1;
                end else if (clk_cnt == 2 * CLK_DIV - 2) begin
                    shift_in <= {shift_in[6:0], miso};
                end else if (clk_cnt == 2 * CLK_DIV - 1) begin
                    sclk <= 1'b0;
                    shift_out <= {shift_out[6:0], 1'b0};
                    clk_cnt <= 4'd0;
                    bit_cnt <= bit_cnt + 1;
                    if (bit_cnt == 8) begin
                        cs_n <= 1'b1;
                        miso_capture <= shift_in;
                        state <= 2'b10; // DONE_ST
                    end
                end
                clk_cnt <= clk_cnt + 1;
            end
            2'b10: begin // DONE_ST
                done <= 1'b1;
                state <= 2'b00; // IDLE
            end
        endcase
    end
end

endmodule