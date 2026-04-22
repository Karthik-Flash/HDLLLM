module spi_master_8bit #(parameter CLK_DIV = 4) (
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

  reg [1:0] state;
  reg [7:0] shift_out, shift_in;
  reg [3:0] clk_cnt, bit_cnt;

  localparam IDLE = 2'd0;
  localparam ACTIVE = 2'd1;
  localparam DONE_ST = 2'd2;

  always @(posedge clk or posedge rst) begin
    if (rst) begin
      state <= IDLE;
      sclk <= 0;
      cs_n <= 1;
      mosi <= 0;
      done <= 0;
      miso_capture <= 0;
      shift_out <= 0;
      shift_in <= 0;
      clk_cnt <= 0;
      bit_cnt <= 0;
    end else begin
      case (state)
        IDLE: begin
          cs_n <= 1;
          sclk <= 0;
          done <= 0;
          if (start) begin
            cs_n <= 0;
            shift_out <= mosi_data;
            bit_cnt <= 0;
            clk_cnt <= 0;
            state <= ACTIVE;
          end
        end
        ACTIVE: begin
          if (clk_cnt < CLK_DIV - 1) begin
            sclk <= 0;
            mosi <= shift_out[7];
          end else if (clk_cnt == CLK_DIV - 1) begin
            sclk <= 1;
          end else if (clk_cnt >= CLK_DIV) begin
            sclk <= 1;
          end else if (clk_cnt == 2 * CLK_DIV - 2) begin
            shift_in <= {shift_in[6:0], miso};
          end else if (clk_cnt == 2 * CLK_DIV - 1) begin
            sclk <= 0;
            shift_out <= {shift_out[6:0], 1'b0};
            clk_cnt <= 0;
            bit_cnt <= bit_cnt + 1;
          end else begin
            sclk <= 0;
            mosi <= shift_out[7];
          end
          clk_cnt <= clk_cnt + 1;
          if (bit_cnt == 8) begin
            cs_n <= 1;
            miso_capture <= shift_in;
            state <= DONE_ST;
          end
        end
        DONE_ST: begin
          done <= 1;
          state <= IDLE;
        end
        default: begin
          state <= IDLE;
        end
      endcase
    end
  end

endmodule