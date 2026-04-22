module spi_master_8bit (
  parameter CLK_DIV = 4,
  input clk, rst, start,
  input [7:0] mosi_data,
  input miso,
  output sclk, cs_n, mosi, done,
  output [7:0] miso_capture
);

reg [1:0] fsm_state;
reg [7:0] shift_out, shift_in;
reg [3:0] clk_cnt, bit_cnt;

always @(posedge rst or posedge clk) begin
  if (rst) begin
    fsm_state <= 2'd0;
    cs_n <= 1'b1;
    sclk <= 1'b0;
    done <= 1'b0;
    shift_out <= 8'h00;
    shift_in <= 8'h00;
    clk_cnt <= 4'h0;
    bit_cnt <= 4'h0;
  end
  else if (start) begin
    fsm_state <= 2'd1; // ACTIVE
    cs_n <= 1'b0;
    shift_out <= mosi_data;
    bit_cnt <= 4'h0;
    clk_cnt <= 4'h0;
  end
end

always @(posedge clk) begin
  case (fsm_state)
    2'd0: // IDLE
      sclk <= 1'b0;
      done <= 1'b0;
    2'd1: // ACTIVE
      if (clk_cnt < CLK_DIV) begin
        sclk <= 1'b0;
        mosi <= shift_out[7];
      end else if (clk_cnt == CLK_DIV-1) begin
        sclk <= 1'b1;
      end else if (clk_cnt >= CLK_DIV && clk_cnt < 2*CLK_DIV-2) begin
        sclk <= 1'b1;
      end else if (clk_cnt == 2*CLK_DIV-2) begin
        shift_in[7:0] <= {shift_in[6:0], miso};
      end else if (clk_cnt == 2*CLK_DIV-1) begin
        sclk <= 1'b0;
        shift_out[7:0] <= {shift_out[6:0], 1'b0};
        clk_cnt <= 4'h0;
        bit_cnt <= bit_cnt + 1;
      end
    2'd2: // DONE_ST
      done <= 1'b1;
  endcase

  if (bit_cnt == 8) begin
    fsm_state <= 2'd2; // DONE_ST
    miso_capture <= shift_in;
    cs_n <= 1'b1;
  end else if (fsm_state == 2'd1 && clk_cnt < CLK_DIV-1) begin
    fsm_state <= 2'd0; // IDLE
  end

  if (clk_cnt < 4'hF) begin
    clk_cnt <= clk_cnt + 1;
  end
end

endmodule