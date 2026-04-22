module uart_rx (
  input clk,
  input rst,
  input rx,
  output reg [7:0] rx_data,
  output reg data_valid
);

  parameter CLKS_PER_BIT = 4;

  reg [7:0] rx_shift;
  reg [2:0] bit_count;
  reg state;
  reg sample;

  // State definitions
  localparam IDLE = 0;
  localparam START = 1;
  localparam DATA = 2;
  localparam STOP = 3;

  always @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      rx_data <= 8'h00;
      data_valid <= 1'b0;
      bit_count <= 0;
    end else begin
      case (state)
        IDLE: begin
          if (!rx) begin
            state <= START;
            sample <= 1'b0;
          end else begin
            state <= IDLE;
            sample <= 1'b1;
          end
        end
        START: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= START;
          end else begin
            state <= DATA;
            bit_count <= 0;
            rx_shift <= rx;
          end
        end
        DATA: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= DATA;
          end else begin
            bit_count <= bit_count + 1;
            rx_shift <= {rx_shift[6:0], rx};
            state <= DATA;
          end
        end
        STOP: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= STOP;
          end else begin
            if (!rx) begin
              state <= IDLE;
            end else begin
              state <= IDLE;
              data_valid <= 1'b1;
            end
          end
        end
        default: begin
          state <= IDLE;
        end
      endcase
    end
  end

  always @(posedge clk) begin
    if (rst) begin
      rx_data <= 8'h00;
    end else if (state == DATA) begin
      if (bit_count == 7) begin
        rx_data <= rx_shift;
        state <= STOP;
      end
    end
  end

  always @(posedge clk) begin
    if (rst) begin
      data_valid <= 1'b0;
    end else if (state == STOP && bit_count == CLKS_PER_BIT/2 -1) begin
      data_valid <= 1'b1;
    end else if (state == IDLE) begin
      data_valid <= 1'b0;
    end
  end

endmodule