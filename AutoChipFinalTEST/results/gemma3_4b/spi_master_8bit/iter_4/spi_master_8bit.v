module spi_master_8bit (
  input clk,
  input rst,
  input start,
  input [7:0] mosi_data,
  input miso,
  output reg sclk,
  output reg cs_n,
  output reg mosi,
  output reg [7:0] miso_capture,
  output reg done
);

  parameter CLK_DIV = 4;

  reg [7:0] shift_out, shift_in;
  reg [3:0] clk_cnt, bit_cnt;

  // IDLE state
  reg [1:0] state;

  always @(posedge clk or negedge rst) begin
    if (rst) begin
      state <= 2'd0;
      sclk <= 1'b0;
      cs_n <= 1'b1;
      mosi <= 1'b0;
      miso_capture <= 8'b0;
      done <= 1'b0;
      shift_out <= 8'b0;
      shift_in <= 8'b0;
      clk_cnt <= 4'b0;
      bit_cnt <= 4'b0;
    end else begin
      case (state)
        2'd0: begin
          cs_n <= 1'b1;
          sclk <= 1'b0;
          done <= 1'b0;
          shift_out <= 8'b0;
          shift_in <= 8'b0;
          clk_cnt <= 4'b0;
          bit_cnt <= 4'b0;
          if (start) begin
            state <= 2'd1;
            shift_out <= mosi_data;
            clk_cnt <= 4'b0;
            bit_cnt <= 4'b0;
          end
        end
        2'd1: begin
          if (clk_cnt < CLK_DIV - 1) begin
            sclk <= 1'b0;
            mosi <= shift_out[7];
            clk_cnt <= clk_cnt + 1;
          end else if (clk_cnt == CLK_DIV - 1) begin
            sclk <= 1'b1;
            clk_cnt <= 4'b0;
          end else begin
            sclk <= 1'b0;
            clk_cnt <= 4'b0;
            bit_cnt <= bit_cnt + 1;
            if (bit_cnt == 8) begin
              state <= 2'd2;
              miso_capture <= shift_in;
              done <= 1'b1;
            end
          end
        end
        2'd2: begin
          done <= 1'b0;
          sclk <= 1'b0;
          cs_n <= 1'b1;
          state <= 2'd0;
        end
        default: begin
          state <= 2'd0;
        end
      endcase
    end
  end

endmodule