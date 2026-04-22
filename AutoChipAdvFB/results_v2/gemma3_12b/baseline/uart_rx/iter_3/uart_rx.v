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
  localparam START_BIT = 1;
  localparam DATA_RECEIVE = 2;
  localparam STOP_BIT = 3;

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
            state <= START_BIT;
          end else begin
            state <= IDLE;
          end
        end
        START_BIT: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= START_BIT;
          end else begin
            state <= DATA_RECEIVE;
            bit_count <= 0;
            rx_shift <= rx;
          end
        end
        DATA_RECEIVE: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= DATA_RECEIVE;
          end else begin
            bit_count <= bit_count + 1;
            rx_shift <= {rx_shift[6:0], rx};
            state <= DATA_RECEIVE;
          end
        end
        STOP_BIT: begin
          if (bit_count < CLKS_PER_BIT/2) begin
            bit_count <= bit_count + 1;
            state <= STOP_BIT;
          end else begin
            if (rx) begin
              state <= IDLE;
              data_valid <= 1'b1;
            end else begin
              state <= IDLE;
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
    end else if (state == DATA_RECEIVE) begin
      if (bit_count == 7) begin
        rx_data <= rx_shift;
        state <= STOP_BIT;
      end
    end
  end

  always @(posedge clk) begin
    if (rst) begin
      data_valid <= 1'b0;
    end else if (state == STOP_BIT && bit_count == CLKS_PER_BIT/2 - 1) begin
      data_valid <= 1'b1;
    end else if (state == IDLE) begin
      data_valid <= 1'b0;
    end
  end

endmodule