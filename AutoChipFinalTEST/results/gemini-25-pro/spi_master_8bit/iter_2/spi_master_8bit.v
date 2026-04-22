module spi_master_8bit #(
  parameter CLK_DIV = 4
) (
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

  localparam IDLE    = 2'd0;
  localparam ACTIVE  = 2'd1;
  localparam DONE_ST = 2'd2;

  reg [1:0] state;
  reg [7:0] shift_out;
  reg [7:0] shift_in;
  reg [3:0] clk_cnt;
  reg [3:0] bit_cnt;

  always @(posedge clk or posedge rst) begin
    if (rst) begin
      state <= IDLE;
      sclk <= 1'b0;
      cs_n <= 1'b1;
      mosi <= 1'b0;
      done <= 1'b0;
      miso_capture <= 8'd0;
      shift_out <= 8'd0;
      shift_in <= 8'd0;
      clk_cnt <= 4'd0;
      bit_cnt <= 4'd0;
    end else begin
      // Default assignments
      done <= 1'b0;

      case (state)
        IDLE: begin
          sclk <= 1'b0;
          cs_n <= 1'b1;
          mosi <= 1'b0;
          if (start) begin
            cs_n <= 1'b0;
            shift_out <= mosi_data;
            mosi <= mosi_data[7];
            bit_cnt <= 4'd0;
            clk_cnt <= 4'd0;
            shift_in <= 8'd0;
            state <= ACTIVE;
          end
        end

        ACTIVE: begin
          clk_cnt <= clk_cnt + 1;

          // SCLK rising edge & MISO sample (CPHA=0)
          if (clk_cnt == CLK_DIV - 1) begin
            sclk <= 1'b1;
            shift_in <= {shift_in[6:0], miso};
          end

          // SCLK falling edge and end of bit cycle
          if (clk_cnt == 2 * CLK_DIV - 1) begin
            sclk <= 1'b0;
            clk_cnt <= 4'd0;
            shift_out <= {shift_out[6:0], 1'b0};
            mosi <= shift_out[6]; // Setup MOSI for next bit

            if (bit_cnt == 4'd7) begin // 8th bit has been transferred
              cs_n <= 1'b1;
              state <= DONE_ST;
            end else begin
              bit_cnt <= bit_cnt + 1;
            end
          end
        end

        DONE_ST: begin
          done <= 1'b1;
          miso_capture <= shift_in;
          state <= IDLE;
        end

        default: begin
          state <= IDLE;
        end
      endcase
    end
  end

endmodule